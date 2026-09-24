"""Isolation boundary tests. Docker integration is opt-in, uses no model calls."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from isolated import CandidateError, CandidateTimeout, DockerInvoker, IsolationError, PINNED_IMAGE, _bounded, parse_response


class RpcTests(unittest.TestCase):
    def test_protocol_rejects_noise_nonfinite_and_wrong_fields(self):
        for raw in [b'noise\n{"rpc_version":1,"ok":true,"result":1}',
                    b'{"rpc_version":1,"ok":true,"result":NaN}',
                    b'{"rpc_version":1,"ok":true,"result":1,"oracle":true}',
                    b'{"rpc_version":true,"ok":true,"result":1}']:
            with self.subTest(raw=raw), self.assertRaises(CandidateError):
                parse_response(raw)
        self.assertEqual(parse_response(b'{"rpc_version":1,"ok":true,"result":{"a":2}}'), {"a": 2})

    def test_candidate_exception_does_not_return_result(self):
        with self.assertRaisesRegex(CandidateError, "ValueError"):
            parse_response(b'{"rpc_version":1,"ok":false,"error":"ValueError: broken"}')

    def test_output_and_time_limits(self):
        with self.assertRaises(ValueError):
            _bounded([sys.executable, "-c", "import os; os.write(1,b'x'*10000)"], max_bytes=100)
        with self.assertRaises(TimeoutError):
            _bounded([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.05)


class InvokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        for role in ("db", "api", "consumer"):
            (self.candidate / (role + ".py")).write_text("# fixture\n")
        self.database_dir = self.root / "db"
        self.database_dir.mkdir()
        self.conn = sqlite3.connect(self.database_dir / "state.sqlite")
        self.conn.execute("CREATE TABLE original(value INTEGER)")
        self.conn.commit()
        self.commands = []

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def fake(self, cmd, **kwargs):
        self.commands.append((cmd, kwargs))
        if cmd[1] == "exec":
            return 0, b'{"rpc_version":1,"ok":true,"result":{"ok":true}}', b''
        return 0, b'container-id\n', b''

    def test_mounts_only_snapshot_driver_database_and_readonly_consumer(self):
        (self.candidate / "oracle-secret.txt").write_text("never mount")
        with DockerInvoker(self.candidate, command_runner=self.fake) as inv:
            self.assertEqual(sorted(p.name for p in inv.snapshot.iterdir()), ["api.py", "consumer.py", "db.py"])
            inv("db", "expand", self.conn)
            inv("consumer", "consume", self.conn, {"payload": {}})
            starts = [cmd for cmd, _ in self.commands if cmd[1] == "run"]
            self.assertEqual(len(starts), 2)
            for command in starts:
                self.assertIn("--network=none", command)
                self.assertIn("--read-only", command)
                self.assertIn("--cap-drop=ALL", command)
                self.assertNotIn(str(self.candidate), " ".join(command))
            self.assertIn(str(self.database_dir.resolve()) + ":/db:rw", starts[0])
            self.assertIn(str(self.database_dir.resolve()) + ":/db:ro", starts[1])

    def test_no_host_transaction_or_incidental_host_files(self):
        with DockerInvoker(self.candidate, command_runner=self.fake) as inv:
            self.conn.execute("INSERT INTO original VALUES (1)")
            with self.assertRaisesRegex(IsolationError, "host transaction"):
                inv("db", "expand", self.conn)
            self.conn.rollback()
            (self.database_dir / "oracle.json").write_text("secret")
            with self.assertRaisesRegex(IsolationError, "only SQLite"):
                inv("db", "expand", self.conn)
        self.assertFalse(self.commands)

    def test_rejects_candidate_symlinks_and_unpinned_image(self):
        (self.candidate / "api.py").unlink()
        (self.candidate / "api.py").symlink_to(self.candidate / "db.py")
        with self.assertRaises(IsolationError):
            DockerInvoker(self.candidate, command_runner=self.fake)
        with self.assertRaises(IsolationError):
            DockerInvoker(self.candidate, image="python:latest", command_runner=self.fake)

    def test_unattributed_timeout_is_unscored_and_destroys_container(self):
        def timeout(command, **kwargs):
            if command[1] == "exec":
                raise TimeoutError("transport deadline")
            return self.fake(command, **kwargs)
        with DockerInvoker(self.candidate, command_runner=timeout) as invoke:
            with self.assertRaises(CandidateTimeout) as caught:
                invoke("db", "expand", self.conn)
            self.assertTrue(caught.exception.infrastructure_error)
            self.assertFalse(invoke.containers)
        self.assertTrue(any(command[1:3] == ["rm", "-f"] for command, _ in self.commands))


@unittest.skipUnless(os.environ.get("LIVEMIGRATE_DOCKER_TESTS") == "1", "opt-in local Docker test")
class DockerIntegrationTests(unittest.TestCase):
    def test_candidate_is_separate_and_consumer_cannot_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            candidate.mkdir()
            (candidate / "db.py").write_text('''
def expand(conn):
    import os
    conn.execute("CREATE TABLE actual(value INTEGER)")
    conn.execute("INSERT INTO actual VALUES (7)")
    print("suppressed normal print")
    try:
        child = os.fork()
    except OSError:
        blocked_fork = True
    else:
        if child == 0:
            os._exit(0)
        os.waitpid(child, 0)
        blocked_fork = False
    return {"oracle_visible": os.path.exists("/oracle"), "uid": os.getuid(), "blocked_fork": blocked_fork}
''')
            (candidate / "api.py").write_text('''
def handle(conn, request, phase):
    conn.execute("INSERT INTO actual VALUES (99)")
    raise ValueError("rollback this write")
''')
            (candidate / "consumer.py").write_text('''
def consume(conn, event):
    import sqlite3
    try:
        bypass = sqlite3.connect("/db/state.sqlite")
        bypass.execute("INSERT INTO actual VALUES (88)")
        bypass.commit()
        wrote = True
    except sqlite3.OperationalError:
        wrote = False
    return {"value": conn.execute("SELECT value FROM actual").fetchone()[0], "bypass_wrote": wrote}
''')
            database = root / "database"
            database.mkdir()
            conn = sqlite3.connect(database / "state.sqlite")
            conn.execute("CREATE TABLE initial(value INTEGER)")
            conn.commit()
            try:
                with DockerInvoker(candidate, PINNED_IMAGE) as invoke:
                    result = invoke("db", "expand", conn)
                    self.assertEqual(result, {"oracle_visible": False, "uid": 65534, "blocked_fork": True})
                    self.assertEqual(conn.execute("SELECT value FROM actual").fetchall(), [(7,)])
                    with self.assertRaisesRegex(CandidateError, "rollback this write"):
                        invoke("api", "handle", conn, {}, "overlap")
                    self.assertEqual(conn.execute("SELECT value FROM actual").fetchall(), [(7,)])
                    self.assertEqual(invoke("consumer", "consume", conn, {}), {"value": 7, "bypass_wrote": False})
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

"""Isolation boundary tests. Docker integration is opt-in, uses no model calls."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from isolated import CandidateError, CandidateTimeout, DockerInvoker, MultiStoreInvoker, IsolationError, PINNED_IMAGE, _bounded, parse_response


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

    def test_pool_keeps_distinct_stores_reuses_containers_and_preserves_consume_readonly(self):
        second_dir = self.root / "second-db"
        second_dir.mkdir()
        second = sqlite3.connect(second_dir / "state.sqlite")
        second.execute("CREATE TABLE other(value INTEGER)")
        second.commit()
        helper = self.root / "public_legacy.py"
        helper.write_text("# public helper only\n")
        try:
            with MultiStoreInvoker(self.candidate, command_runner=self.fake, legacy_helper=helper) as inv:
                inv("consumer", "on_message", self.conn, {"kind": "prepare"})
                inv("db", "on_message", second, {"kind": "prepare"})
                inv("consumer", "on_message", self.conn, {"kind": "commit"})
                inv("consumer", "consume", self.conn, {})
                inv("api", "on_message", second, {"kind": "commit"})
                self.assertEqual(len(inv.stores), 2)
                starts = [command for command, _ in self.commands if command[1] == "run"]
                self.assertEqual(len(starts), 3)
                volumes = [command[command.index("--volume") + 1] for command in starts]
                self.assertEqual(volumes, [str(self.database_dir.resolve()) + ":/db:rw",
                                          str(second_dir.resolve()) + ":/db:rw",
                                          str(self.database_dir.resolve()) + ":/db:ro"])
                self.assertTrue(all(command.count("--volume") == 1 for command in starts))
                for child in inv.stores.values():
                    self.assertEqual((child.snapshot / "legacy.py").read_text(), helper.read_text())
                    self.assertEqual((child.snapshot / "legacy.py").stat().st_mode & 0o777, 0o444)
                self.assertFalse(any(str(helper) in " ".join(command) for command in starts))
            removed = [command for command, _ in self.commands if command[1:3] == ["rm", "-f"]]
            self.assertEqual(len(removed), 3)
            self.assertFalse(inv.stores)
        finally:
            second.close()

    def test_pool_store_limit_cleans_up_and_legacy_path_is_not_candidate_selected(self):
        second_dir = self.root / "second-db"
        second_dir.mkdir()
        second = sqlite3.connect(second_dir / "state.sqlite")
        second.execute("CREATE TABLE other(value INTEGER)")
        second.commit()
        try:
            with MultiStoreInvoker(self.candidate, command_runner=self.fake, max_stores=1) as inv:
                inv("db", "on_message", self.conn, {})
                with self.assertRaisesRegex(IsolationError, "store limit"):
                    inv("db", "on_message", second, {})
            self.assertFalse(inv.stores)
            self.assertEqual(len([command for command, _ in self.commands if command[1] == "run"]), 1)
            self.assertEqual(len([command for command, _ in self.commands if command[1] == "rm"]), 1)
            helper = self.root / "helper-link.py"
            helper.symlink_to(self.candidate / "db.py")
            with self.assertRaisesRegex(IsolationError, "regular public"):
                DockerInvoker(self.candidate, command_runner=self.fake, legacy_helper=helper)
        finally:
            second.close()


@unittest.skipUnless(os.environ.get("LIVEMIGRATE_DOCKER_TESTS") == "1", "opt-in local Docker test")
class DockerIntegrationTests(unittest.TestCase):
    def test_four_stores_writable_messages_and_readonly_consume_with_public_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate"
            candidate.mkdir()
            helper = root / "immutable_v1.py"
            helper.write_text('''
def bump(conn, delta):
    conn.execute("UPDATE actual SET value=value+?", (delta,))
    return conn.execute("SELECT value FROM actual").fetchone()[0]
''')
            source = '''
import legacy
def on_message(conn, message):
    import os
    value = legacy.bump(conn, message["delta"])
    return {"value": value, "files": sorted(os.listdir("/db"))}
def consume(conn, event):
    import sqlite3
    blocked = []
    for database in (conn, sqlite3.connect("/db/state.sqlite")):
        try:
            database.execute("UPDATE actual SET value=999")
            database.commit()
            blocked.append(False)
        except sqlite3.OperationalError:
            blocked.append(True)
    return {"value": conn.execute("SELECT value FROM actual").fetchone()[0], "blocked": blocked}
'''
            for role in ("db", "api", "consumer"):
                (candidate / (role + ".py")).write_text(source)
            connections = []
            try:
                for index in range(4):
                    store = root / ("store-" + str(index))
                    store.mkdir()
                    conn = sqlite3.connect(store / "state.sqlite")
                    conn.execute("CREATE TABLE actual(value INTEGER)")
                    conn.execute("INSERT INTO actual VALUES (?)", (10 + index,))
                    conn.commit()
                    connections.append(conn)
                with MultiStoreInvoker(candidate, legacy_helper=helper) as invoke:
                    for role, conn, expected in zip(("api", "db", "consumer", "consumer"), connections, (11, 12, 13, 14)):
                        result = invoke(role, "on_message", conn, {"delta": 1})
                        self.assertEqual(result["value"], expected)
                        self.assertTrue(set(result["files"]) <= {"state.sqlite", "state.sqlite-journal", "state.sqlite-wal", "state.sqlite-shm"})
                    self.assertEqual(invoke("consumer", "on_message", connections[2], {"delta": 2})["value"], 15)
                    self.assertEqual(invoke("consumer", "consume", connections[2], {}), {"value": 15, "blocked": [True, True]})
                    self.assertEqual(len(invoke.stores), 4)
                    self.assertEqual(sum(len(child.containers) for child in invoke.stores.values()), 5)
                self.assertFalse(invoke.stores)
                self.assertEqual([conn.execute("SELECT value FROM actual").fetchone()[0] for conn in connections], [11, 12, 15, 14])
            finally:
                for conn in connections:
                    conn.close()

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

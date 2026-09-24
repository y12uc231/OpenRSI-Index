"""Offline harness tests. No Docker, model forward pass, or candidate import."""
import base64
import copy
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest import mock

import controller_driver as driver
import feedback
import launcher
import wire


class WireAndDriverTests(unittest.TestCase):
    def test_frames_are_bounded_and_strict(self):
        self.assertEqual(wire.read(io.BytesIO(wire.pack({"x": [1, True]}))), {"x": [1, True]})
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ValueError):
                wire.decode(raw)
        with self.assertRaises(ValueError):
            wire.read(io.BytesIO(struct.pack("!I", wire.MAX_FRAME + 1)))
        with self.assertRaises(EOFError):
            wire.read(io.BytesIO(b"\x00\x00"))

    def test_fragmented_header(self):
        class Short(io.BytesIO):
            def read(self, size=-1):
                return super().read(min(size, 1))
        self.assertEqual(wire.read(Short(wire.pack({"x": 1}))), {"x": 1})

    def test_vectors_and_masks(self):
        encoded = {"dtype": "f4", "size": 2, "data": base64.b64encode(struct.pack("<ff", 1.5, -2)).decode()}
        self.assertEqual(driver.vector(encoded, "f4"), [1.5, -2.0])
        with self.assertRaises(ValueError):
            driver.vector({"dtype": "u1", "size": 1, "data": base64.b64encode(b"\x02").decode()}, "u1")
        with self.assertRaises(ValueError):
            driver.vector(encoded | {"size": 3}, "f4")

    def test_action_memory_validity(self):
        self.assertEqual(driver.candidate_response({"action": 1, "memory": {}}, [False, True]), (1, {}))
        for action in (0, True, 3, "1"):
            with self.assertRaises(ValueError):
                driver.candidate_response({"action": action, "memory": {}}, [False, True])
        with self.assertRaises(ValueError):
            driver.bounded_memory("a" * 65536)
        with self.assertRaises(ValueError):
            driver.bounded_memory(float("nan"))

    def test_worker_error_attribution(self):
        self.assertEqual(launcher.worker_error(TimeoutError())["status"], "infrastructure_or_incomplete")
        self.assertEqual(launcher.worker_error(EOFError())["status"], "infrastructure_or_incomplete")
        self.assertEqual(launcher.worker_error(ValueError())["status"], "candidate_invalid")
        response = {"error": {"status": "candidate_invalid", "code": "candidate_act", "error_type": "PrivateErrorName"}}
        self.assertEqual(launcher.checked_worker_reply(response)["error"]["error_type"], "CandidateError")


class SandboxTests(unittest.TestCase):
    def test_worker_has_only_candidate_driver_and_wire_mounts(self):
        command = launcher.worker_args("test-worker", Path("/public/snapshot"))
        mounts = [command[i + 1] for i, value in enumerate(command) if value == "--mount"]
        self.assertEqual(len(mounts), 3)
        self.assertTrue(all(x.endswith(",readonly") for x in mounts))
        self.assertEqual({x.split("dst=")[1].split(",")[0] for x in mounts},
                         {"/candidate", "/driver/controller_driver.py", "/driver/wire.py"})
        for flag in ("--network", "--ipc"):
            self.assertEqual(command[command.index(flag) + 1], "none")
        self.assertIn("--read-only", command)
        self.assertEqual(command[command.index("--user") + 1], "65534:65534")
        self.assertIn("PYTHONHASHSEED=0", command)

    def test_engine_does_not_mount_candidate(self):
        args = SimpleNamespace(source=Path("/source"), assets=Path("/assets"), output=Path("/output"), environment_image="sha256:" + "1" * 64, suite="dev")
        command = launcher.engine_args("test-engine", args)
        mounts = [command[i + 1] for i, value in enumerate(command) if value == "--mount"]
        self.assertFalse(any("/candidate" in mount for mount in mounts))
        self.assertEqual(sum("readonly" not in mount for mount in mounts), 1)

    def exercise(self, invalid=False, broken=False, changed=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            candidate.mkdir()
            (candidate / "controller.py").write_text("raise AssertionError('candidate must never be host imported')\n")
            args = SimpleNamespace(source=root / "source", assets=root / "assets", candidate=candidate,
                                   output=root / "new-output", suite="dev", timeout=10800,
                                   environment_image="sha256:" + "1" * 64)
            cases = []
            messages = []
            for index, world in enumerate(launcher.SUITES["dev"]):
                case = launcher.incomplete_case(world, "candidate_act" if invalid else None)
                case.update(status="candidate_invalid" if invalid else "scored", score=None if invalid else 0.25,
                            steps=1, naturally_terminated=True, metrics={} if invalid else {"Team/coord_reward_pct_of_max": 0.25})
                cases.append(case)
                messages.append({"kind": "initialize", "world_id": world, "actors": 3, "schema": {}})
                messages.append({"kind": "actions", "packets": [{"step": 0, "sentinel": actor} for actor in range(3)]})
                messages.append({"kind": "world_result", "world_id": world, "result": case})
            messages.append({"kind": "done", "status": "unscored" if invalid else "scored", "total": 4, "scored": 0 if invalid else 4})
            raw = {"schema_version": 1, "status": "unscored" if invalid else "scored", "suite": "dev",
                   "world_ids": launcher.SUITES["dev"], "cases": cases, "total": 4, "scored": 0 if invalid else 4,
                   "primary_score": None if invalid else 0.25, "metrics_mean": {} if invalid else {"Team/coord_reward_pct_of_max": 0.25}}
            instances = []
            class FakeProcess:
                def __init__(self, command, log):
                    self.is_engine = "/harness/engine.py" in command
                    self.sent, self.closed = [], False
                    self.proc = SimpleNamespace(wait=lambda timeout: 0)
                    self.messages = iter(messages)
                    instances.append(self)
                    if self.is_engine:
                        (args.output / "engine-result.private.json").write_text(json.dumps(raw))
                def send(self, value, timeout):
                    self.sent.append(copy.deepcopy(value))
                def recv(self, timeout):
                    if self.is_engine:
                        if broken:
                            raise TimeoutError("synthetic instrumentation interruption")
                        return next(self.messages)
                    if self.sent[-1]["kind"] == "initialize":
                        return {"ready": True}
                    if invalid:
                        return {"error": {"status": "candidate_invalid", "code": "candidate_act", "error_type": "ValueError"}}
                    return {"action": 0}
                def close(self):
                    self.closed = True
                def stats(self):
                    return {"read_bytes": 0, "written_bytes": 0, "stderr_bytes": 0, "stderr_truncated": False}
            before = {"candidate_sha256": launcher.digest(candidate / "controller.py")}
            after = before | ({"changed": True} if changed else {})
            with mock.patch.object(launcher, "provenance", side_effect=[before, after]), mock.patch.object(launcher.subprocess, "run") as run:
                result = launcher.run(args, process_factory=FakeProcess)
            self.assertTrue(all(p.closed for p in instances))
            saved = json.loads((args.output / "result.json").read_text())
            self.assertEqual(saved, result)
            self.assertEqual(len(result["cases"]), 4)
            if not broken:
                workers = [p for p in instances if not p.is_engine]
                self.assertEqual(len(workers), 12)
                self.assertEqual(len({id(w) for w in workers}), 12)
                for i, worker in enumerate(workers):
                    self.assertEqual(worker.sent[0]["agent_id"], i % 3)
                    self.assertNotIn("world_id", worker.sent[0])
                    self.assertEqual(worker.sent[1]["local"]["sentinel"], i % 3)
            self.assertTrue(all(call.kwargs.get("timeout", 0) <= 30 for call in run.call_args_list))
            return result

    def test_fresh_workers_and_all_worlds_normal_completion(self):
        result = self.exercise()
        self.assertEqual(result["primary_score"], 0.25)
        self.assertTrue(result["provenance_verified"])

    def test_candidate_invalid_is_preserved_with_verified_provenance(self):
        result = self.exercise(invalid=True)
        self.assertEqual(result["status"], "unscored")
        self.assertTrue(result["provenance_verified"])
        self.assertFalse(result["infrastructure_affected"])
        self.assertTrue(all(c["status"] == "candidate_invalid" for c in result["cases"]))

    def test_infrastructure_never_accepts_preexisting_engine_score(self):
        result = self.exercise(broken=True)
        self.assertEqual(result["status"], "unscored")
        self.assertIsNone(result["primary_score"])
        self.assertFalse(result["provenance_verified"])
        self.assertTrue(result["infrastructure_affected"])

    def test_hash_change_invalidates_score(self):
        result = self.exercise(changed=True)
        self.assertEqual(result["status"], "unscored")
        self.assertIsNone(result["primary_score"])
        self.assertFalse(result["provenance_verified"])


class FeedbackTests(unittest.TestCase):
    def test_aggregate_only_and_unverified_score_rejected(self):
        value = {"status": "scored", "total": 1, "primary_score": 0.5, "provenance_verified": True,
                 "metrics_mean": {"Team/coord_reward_pct_of_max": 0.5, "private-path": "not public"},
                 "cases": [{"world_id": 9999, "status": "scored", "observation": "private", "steps": 5}],
                 "commands": ["private-command"], "error": "private-error"}
        public = feedback.public_feedback(value)
        encoded = json.dumps(public)
        self.assertNotIn("private", encoded)
        self.assertNotIn("world_id", encoded)
        self.assertEqual(public["primary_score"], 0.5)
        self.assertIsNone(feedback.public_feedback(value | {"provenance_verified": False})["primary_score"])

    def test_safe_builtin_error_counts(self):
        result = {"status": "unscored", "total": 2, "cases": [
            {"status": "candidate_invalid", "error_type": "TypeError", "diagnostic_code": "candidate_act"},
            {"status": "candidate_invalid", "error_type": "PrivateClassName", "diagnostic_code": "candidate_act"}]}
        public = feedback.public_feedback(result)
        self.assertEqual(public["error_type_counts"], {"TypeError": 1, "other": 1})
        self.assertNotIn("PrivateClassName", json.dumps(public))


@unittest.skipUnless(os.environ.get("ALEM_DOCKER_TESTS") == "1", "explicit Docker probe opt-in")
class DockerSandboxTests(unittest.TestCase):
    def test_mount_process_and_episode_isolation(self):
        # Trusted diagnostic source, no policy/model execution. Never imported
        # on the host. Separate instances establish private and fresh /tmp.
        source = '''import os, random
count = 0
def initialize(agent_id, schema):
    assert not os.path.exists('/app') and not os.path.exists('/assets')
    assert not os.path.exists('/tmp/actor-sentinel')
    assert os.listdir('/candidate') == ['controller.py']
    assert random.random() == 0.8444218515250481
    try:
        open('/candidate/controller.py', 'a')
    except OSError:
        pass
    else:
        raise AssertionError('candidate mount writable')
    try:
        pid = os.fork()
    except OSError:
        pass
    else:
        if pid == 0: os._exit(1)
        raise AssertionError('fork permitted')
    with open('/tmp/actor-sentinel','w') as f: f.write(str(agent_id))
    return {'agent': agent_id, 'count': 0}
def act(local, memory):
    global count
    assert int(open('/tmp/actor-sentinel').read()) == memory['agent']
    assert memory['count'] == count
    count += 1
    return {'action': 0, 'memory': {'agent': memory['agent'], 'count': count}}
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            snapshot = root / "candidate"
            snapshot.mkdir(mode=0o755)
            (snapshot / "controller.py").write_text(source)
            (snapshot / "controller.py").chmod(0o444)
            active = []
            try:
                for index, actor in enumerate((0, 1, 0)):
                    name = "alem-sandbox-test-" + uuid.uuid4().hex[:12]
                    worker = launcher.FrameProcess(launcher.worker_args(name, snapshot), root / f"worker-{index}.stderr.txt")
                    active.append((name, worker))
                    worker.send({"kind": "initialize", "agent_id": actor, "schema": {}}, timeout=30)
                    self.assertEqual(worker.recv(timeout=30), {"ready": True})
                    def encoded(kind, raw, size):
                        return {"dtype": kind, "data": base64.b64encode(raw).decode(), "size": size}
                    packet = {"observation": encoded("f4", struct.pack("<f", 0), 1),
                              "legal_mask": encoded("u1", b"\x01", 1), "frozen_logits": encoded("f4", struct.pack("<f", 0), 1),
                              "proposal": 0, "previous_reward": 0, "step": 0}
                    for step in range(2):
                        worker.send({"kind": "act", "local": packet | {"step": step}}, timeout=30)
                        self.assertEqual(worker.recv(timeout=30), {"action": 0})
            finally:
                for name, worker in active:
                    worker.close()
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)


if __name__ == "__main__":
    unittest.main()

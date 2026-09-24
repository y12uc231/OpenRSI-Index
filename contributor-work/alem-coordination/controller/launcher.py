"""Portable candidate-only Alem evaluation with fresh actor sandboxes per world."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import uuid

from feedback import ERROR_TYPES, public_feedback
from wire import MAX_FRAME, decode, pack

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT.parent / "baseline"
WORKER_IMAGE = "python@sha256:23b5dc88c7dd47fec3f960b51dc30d19df9875cfbfc60f3b62d3e5b88cbccf62"
SUITES = {"dev": list(range(20000, 20004)), "evaluation": list(range(9999, 10019))}
MAX_CANDIDATE = 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def regular(root, name):
    path = root / name
    if not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file():
        raise ValueError("invalid regular manifest file")
    current = path.parent
    while current != root:
        if current.is_symlink():
            raise ValueError("manifest symlink")
        current = current.parent
    return path


def provenance(source, assets, candidate):
    source_spec = json.loads((BASELINE / "source-manifest.json").read_text())
    asset_spec = json.loads((BASELINE / "asset-manifest.json").read_text())
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True, timeout=30).strip()
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=source, timeout=30).decode().split("\0")[:-1]
    untracked = subprocess.check_output(["git", "ls-files", "--others", "-z"], cwd=source, timeout=30)
    if head != source_spec["revision"] or set(tracked) != set(source_spec["files"]) or untracked:
        raise ValueError("source revision or file inventory mismatch")
    source_hashes = {name: digest(regular(source, name)) for name in tracked}
    if source_hashes != source_spec["files"]:
        raise ValueError("source digest mismatch")
    asset_hashes = {}
    for row in asset_spec["files"]:
        if not row["path"].startswith("assets/"):
            raise ValueError("asset path prefix")
        name = row["path"].removeprefix("assets/")
        path = regular(assets, name)
        value = digest(path)
        if path.stat().st_size != row["bytes"] or value != row["sha256"]:
            raise ValueError("asset digest mismatch")
        asset_hashes[name] = value
    controller = regular(candidate, "controller.py")
    if controller.stat().st_size > MAX_CANDIDATE:
        raise ValueError("candidate source exceeds 1MiB")
    own_files = ["launcher.py", "controller_driver.py", "wire.py", "engine.py", "feedback.py", "CONTRACT.md"]
    return {"source_revision": head, "source_sha256": source_hashes,
            "asset_revision": asset_spec["revision"], "asset_sha256": asset_hashes,
            "candidate_sha256": digest(controller),
            "runner_sha256": {name: digest(ROOT / name) for name in own_files},
            "manifest_sha256": {name: digest(BASELINE / name) for name in ("source-manifest.json", "asset-manifest.json")}}


class FrameProcess:
    """Nonblocking bounded frames and bounded local stderr, with timed cleanup."""
    def __init__(self, command, log_path):
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self.rfd, self.wfd = self.proc.stdout.fileno(), self.proc.stdin.fileno()
        os.set_blocking(self.rfd, False)
        os.set_blocking(self.wfd, False)
        self.buffer = b""
        self.read_bytes = self.written_bytes = self.stderr_bytes = 0
        self.log_path = log_path
        self.drain = threading.Thread(target=self._drain, daemon=True)
        self.drain.start()

    def _drain(self):
        with self.log_path.open("wb") as out:
            while True:
                chunk = self.proc.stderr.read(65536)
                if not chunk:
                    break
                room = max(0, MAX_LOG_BYTES - self.stderr_bytes)
                out.write(chunk[:room])
                self.stderr_bytes += len(chunk)

    def send(self, value, timeout=30):
        data, offset = pack(value), 0
        deadline = time.monotonic() + timeout
        while offset < len(data):
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([], [self.wfd], [], left)[1]:
                raise TimeoutError("frame write timeout")
            sent = os.write(self.wfd, data[offset:])
            if not sent:
                raise EOFError("frame write closed")
            offset += sent
            self.written_bytes += sent

    def recv(self, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            if len(self.buffer) >= 4:
                size = struct.unpack("!I", self.buffer[:4])[0]
                if size > MAX_FRAME:
                    raise ValueError("oversized frame")
                if len(self.buffer) >= size + 4:
                    raw, self.buffer = self.buffer[4:size + 4], self.buffer[size + 4:]
                    return decode(raw)
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([self.rfd], [], [], left)[0]:
                raise TimeoutError("frame read timeout")
            data = os.read(self.rfd, 65536)
            if not data:
                raise EOFError("process ended mid-protocol")
            self.buffer += data
            self.read_bytes += len(data)

    def close(self):
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
        self.drain.join(timeout=2)
        if self.proc.stdout:
            self.proc.stdout.close()
        if self.proc.stderr and not self.drain.is_alive():
            self.proc.stderr.close()

    def stats(self):
        return {"read_bytes": self.read_bytes, "written_bytes": self.written_bytes,
                "stderr_bytes": self.stderr_bytes, "stderr_truncated": self.stderr_bytes > MAX_LOG_BYTES}


def worker_args(name, snapshot):
    return ["docker", "run", "--rm", "--pull=never", "--init", "-i", "--name", name,
            "--network", "none", "--ipc", "none", "--read-only", "--user", "65534:65534",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--cpus", "1",
            "--memory", "512m", "--pids-limit", "16", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16777216,uid=65534,gid=65534,mode=700",
            "-e", "PYTHONHASHSEED=0", "--mount", f"type=bind,src={snapshot},dst=/candidate,readonly",
            "--mount", f"type=bind,src={ROOT / 'controller_driver.py'},dst=/driver/controller_driver.py,readonly",
            "--mount", f"type=bind,src={ROOT / 'wire.py'},dst=/driver/wire.py,readonly",
            "--workdir", "/tmp", WORKER_IMAGE, "python", "-B", "/driver/controller_driver.py"]


def engine_args(name, args):
    return ["docker", "run", "--rm", "--pull=never", "-i", "--name", name, "--network", "none",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--cpus", "4", "--memory", "6g", "--pids-limit", "256", "--tmpfs", "/tmp:rw,nosuid,size=1073741824",
            "-e", "JAX_PLATFORM_NAME=cpu", "-e", "WANDB_MODE=disabled", "-e", "MPLCONFIGDIR=/tmp/matplotlib",
            "-e", "XDG_CACHE_HOME=/tmp/cache", "-e", "OMP_NUM_THREADS=4",
            "--mount", f"type=bind,src={args.source},dst=/app,readonly",
            "--mount", f"type=bind,src={args.assets},dst=/assets,readonly",
            "--mount", f"type=bind,src={ROOT / 'engine.py'},dst=/harness/engine.py,readonly",
            "--mount", f"type=bind,src={ROOT / 'wire.py'},dst=/harness/wire.py,readonly",
            "--mount", f"type=bind,src={args.output},dst=/results", "--workdir", "/tmp",
            args.environment_image, "python", "-B", "/harness/engine.py", "--suite", args.suite]


def worker_error(exc):
    if isinstance(exc, TimeoutError):
        return {"status": "infrastructure_or_incomplete", "code": "worker_timeout", "error_type": "TimeoutError"}
    if isinstance(exc, (EOFError, BrokenPipeError, OSError)):
        return {"status": "infrastructure_or_incomplete", "code": "worker_exit", "error_type": type(exc).__name__}
    return {"status": "candidate_invalid", "code": "worker_protocol", "error_type": type(exc).__name__}


def checked_worker_reply(response, initializing=False):
    if isinstance(response, dict) and set(response) == {"error"}:
        error = response["error"]
        if isinstance(error, dict) and set(error) == {"status", "code", "error_type"} and error["status"] in ("candidate_invalid", "infrastructure_or_incomplete") and error["code"] in ("candidate_import", "candidate_initialize", "candidate_act", "candidate_output", "worker_input"):
            error_type = error["error_type"] if error["error_type"] in ERROR_TYPES else "CandidateError" if error["status"] == "candidate_invalid" else "WorkerError"
            return {"error": {"status": error["status"], "code": error["code"], "error_type": error_type}}
        raise ValueError("worker error schema")
    if initializing and response == {"ready": True}:
        return response
    if not initializing and isinstance(response, dict) and set(response) == {"action"} and type(response["action"]) is int:
        return response
    raise ValueError("worker response schema")


def incomplete_case(world_id, code):
    return {"world_id": world_id, "status": "infrastructure_or_incomplete", "steps": 0,
            "naturally_terminated": False, "score": None, "metrics": {}, "diagnostic_code": code,
            "error_type": "InfrastructureError", "seconds": 0, "ipc_seconds": 0,
            "overrides": 0, "action_count": 0, "policy_forward_batches": 0, "controller_calls": 0,
            "native_communication_actions": 0, "trace_sha256": None}


def run(args, process_factory=FrameProcess):
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start + args.timeout
    launch = {"schema_version": 1, "suite": args.suite, "operator_timeout_seconds": args.timeout,
              "worker_image": WORKER_IMAGE, "environment_image": args.environment_image,
              "commands": [], "milestones": [], "process_traffic": [], "llm_calls": 0}
    before = None
    rows, workers, names = {}, [], []
    engine = None
    failure = None
    normal_completion = False
    prefix = "alem-" + uuid.uuid4().hex[:12]
    temp = tempfile.TemporaryDirectory(prefix="alem-candidate-")
    snapshot = Path(temp.name) / "candidate"

    def remaining(limit):
        value = min(limit, deadline - time.monotonic())
        if value <= 0:
            raise TimeoutError("operator deadline")
        return value

    def close_workers():
        for worker in workers:
            try:
                worker.close()
            except Exception:
                launch["cleanup_incomplete"] = True
            finally:
                launch["process_traffic"].append(worker.stats())
        workers.clear()
        for name in list(names):
            try:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                launch["cleanup_incomplete"] = True
            names.remove(name)

    try:
        before = provenance(args.source, args.assets, args.candidate)
        launch["hashes_before"] = before
        snapshot.mkdir(mode=0o755)
        shutil.copyfile(args.candidate / "controller.py", snapshot / "controller.py")
        (snapshot / "controller.py").chmod(0o444)
        if digest(snapshot / "controller.py") != before["candidate_sha256"]:
            raise ValueError("candidate changed during snapshot")
        for image in (args.environment_image, WORKER_IMAGE):
            subprocess.run(["docker", "image", "inspect", image], check=True, capture_output=True, timeout=remaining(30))
        engine_name = prefix + "-engine"
        command = engine_args(engine_name, args)
        launch["commands"].append(command)
        engine = process_factory(command, args.output / "engine.stderr.txt")
        current_world = None
        expected = iter(SUITES[args.suite])
        while True:
            message = engine.recv(timeout=remaining(300))
            if not isinstance(message, dict):
                raise ValueError("engine message schema")
            kind = message.get("kind")
            if kind == "milestone":
                launch["milestones"].append(message)
            elif kind == "initialize":
                close_workers()
                current_world = next(expected)
                if message.get("world_id") != current_world or message.get("actors") != 3:
                    raise ValueError("engine world sequence")
                error = None
                try:
                    for actor in range(3):
                        name = prefix + "-w" + str(current_world) + "-a" + str(actor)
                        names.append(name)
                        command = worker_args(name, snapshot)
                        launch["commands"].append(command)
                        worker = process_factory(command, args.output / f"world-{current_world}-actor-{actor}.stderr.txt")
                        workers.append(worker)
                        worker.send({"kind": "initialize", "agent_id": actor, "schema": message["schema"]}, timeout=remaining(30))
                    for worker in workers:
                        response = checked_worker_reply(worker.recv(timeout=remaining(30)), initializing=True)
                        error = error or response.get("error")
                except Exception as exc:
                    error = worker_error(exc)
                engine.send({"error": error} if error else {"ready": True}, timeout=remaining(30))
            elif kind == "actions":
                packets = message.get("packets")
                if current_world is None or not isinstance(packets, list) or len(packets) != 3 or len(workers) != 3:
                    raise ValueError("engine action sequence")
                actions, error = [], None
                try:
                    for worker, packet in zip(workers, packets):
                        worker.send({"kind": "act", "local": packet}, timeout=remaining(30))
                    for worker in workers:
                        response = checked_worker_reply(worker.recv(timeout=remaining(30)))
                        error = error or response.get("error")
                        if "action" in response:
                            actions.append(response["action"])
                except Exception as exc:
                    error = worker_error(exc)
                engine.send({"error": error} if error else {"actions": actions}, timeout=remaining(30))
            elif kind == "world_result":
                if message.get("world_id") != current_world or current_world in rows or message.get("result", {}).get("world_id") != current_world:
                    raise ValueError("engine result sequence")
                rows[current_world] = message["result"]
                close_workers()
                current_world = None
            elif kind == "done":
                if len(rows) != len(SUITES[args.suite]) or message.get("total") != len(rows):
                    raise ValueError("incomplete engine suite")
                if engine.proc.wait(timeout=remaining(30)) != 0:
                    raise RuntimeError("engine nonzero exit")
                normal_completion = True
                break
            else:
                raise ValueError("unknown engine message")
    except BaseException as exc:
        failure = "operator_timeout" if isinstance(exc, TimeoutError) else "engine_failure"
        launch["error"] = {"code": failure, "error_type": type(exc).__name__, "message": str(exc)}
    finally:
        try:
            close_workers()
        except Exception as exc:
            launch["cleanup_incomplete"] = True
            failure = failure or "engine_failure"
        if engine is not None:
            try:
                engine.close()
                launch["process_traffic"].append(engine.stats())
            except Exception:
                launch["cleanup_incomplete"] = True
        try:
            subprocess.run(["docker", "rm", "-f", prefix + "-engine"], capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            launch["cleanup_incomplete"] = True
        temp.cleanup()
        try:
            after = provenance(args.source, args.assets, args.candidate)
            launch["hashes_after"] = after
            launch["source_candidate_unchanged"] = before is not None and before == after
        except Exception as exc:
            launch["source_candidate_unchanged"] = False
            launch["verification_error_type"] = type(exc).__name__
        if not launch["source_candidate_unchanged"]:
            failure = failure or "source_changed"
        if launch.get("cleanup_incomplete"):
            failure = failure or "engine_failure"
        engine_path = args.output / "engine-result.private.json"
        result = {}
        if normal_completion and not failure:
            try:
                result = decode(engine_path.read_bytes())
                if result.get("world_ids") != SUITES[args.suite] or result.get("cases") != [rows[w] for w in SUITES[args.suite]] or result.get("total") != len(rows):
                    raise ValueError("engine result differs from reported worlds")
                if result.get("status") not in ("scored", "unscored"):
                    raise ValueError("engine status")
            except Exception:
                failure = "engine_failure"
        if not normal_completion:
            failure = failure or "incomplete"
        if failure:
            result = {"schema_version": 1, "status": "unscored", "suite": args.suite,
                      "world_ids": SUITES[args.suite], "total": len(SUITES[args.suite]),
                      "cases": [rows.get(w, incomplete_case(w, failure)) for w in SUITES[args.suite]],
                      "primary_score": None, "metrics_mean": {}, "infrastructure_diagnostic": failure}
            result["scored"] = sum(c["status"] == "scored" for c in result["cases"])
        launch["wall_seconds"] = time.monotonic() - start
        result["host_provenance"] = {key: launch[key] for key in ("worker_image", "environment_image", "source_candidate_unchanged", "operator_timeout_seconds", "wall_seconds", "llm_calls")}
        result["host_provenance"]["hashes"] = before
        result["infrastructure_affected"] = bool(failure or launch.get("cleanup_incomplete"))
        result["provenance_verified"] = bool(normal_completion and not failure and launch["source_candidate_unchanged"])
        path = args.output / "result.json"
        temporary = args.output / "result.tmp.json"
        temporary.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
        temporary.replace(path)
        (args.output / "launch.private.json").write_text(json.dumps(launch, indent=2, sort_keys=True, allow_nan=False) + "\n")
        feedback = public_feedback(result)
        (args.output / "feedback.json").write_text(json.dumps(feedback, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "assets", "candidate", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--environment-image", required=True)
    parser.add_argument("--suite", choices=SUITES, required=True)
    parser.add_argument("--timeout", type=float, default=10800)
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise InterruptedError("operator signal")
    signal.signal(signal.SIGTERM, interrupted)
    if not re.fullmatch(r"(?:sha256:[0-9a-f]{64}|[A-Za-z0-9./:_-]+@sha256:[0-9a-f]{64})", args.environment_image):
        parser.error("environment image must be an immutable Docker ID or digest")
    if not 0 < args.timeout <= 172800:
        parser.error("timeout must be positive and at most 48 hours")
    for name in ("source", "assets", "candidate", "output"):
        path = getattr(args, name).resolve()
        if any(c in str(path) for c in (",", "\n", "\r")):
            parser.error("mount paths cannot contain commas or newlines")
        setattr(args, name, path)
    result = run(args)
    print(json.dumps(public_feedback(result), sort_keys=True, allow_nan=False))
    if not result["provenance_verified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

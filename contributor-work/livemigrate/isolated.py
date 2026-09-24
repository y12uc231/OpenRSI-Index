"""Run LiveMigrate callbacks without placing candidate code in the oracle process.

Only the three submitted callback files, this driver, and one database directory
are mounted. Consumers use a separate container with a read-only database mount.
Each callback starts a fresh interpreter. Persistent state belongs in SQLite.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

PINNED_IMAGE = "python@sha256:23b5dc88c7dd47fec3f960b51dc30d19df9875cfbfc60f3b62d3e5b88cbccf62"
CALLS = {"db": {"expand", "backfill", "contract"}, "api": {"handle"}, "consumer": {"consume"}}
MAX_RPC_BYTES = 1024 * 1024
CORE_ROOT = Path(__file__).resolve().parent


class IsolationError(RuntimeError):
    """Infrastructure or RPC failure; no candidate response was trusted."""
    infrastructure_error = True


class CandidateError(RuntimeError):
    """A callback raised or returned an invalid protocol response."""


class CandidateTimeout(IsolationError):
    """Unattributed RPC deadline; unscored until infrastructure is excluded."""


@contextmanager
def task_runtime(task_root=CORE_ROOT):
    """Load one trusted task's oracle on the host, without import-cache mixing.

    The CLI runs one suite per process. Scope the conventional ``scenarios``
    import to the selected task, then restore any caller's existing module.
    This path is never passed to Docker or added to candidate import paths.
    """
    task_root = Path(task_root).resolve()
    paths = {name: task_root / (name + ".py") for name in ("runtime", "scenarios")}
    for name, path in paths.items():
        if not path.is_file():
            raise IsolationError("task root requires " + name + ".py")
    old_scenarios = sys.modules.get("scenarios")
    names = []

    def load(name):
        unique = "livemigrate_task_" + name + "_" + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(unique, paths[name])
        module = importlib.util.module_from_spec(spec)
        names.append(unique)
        sys.modules[unique] = module
        spec.loader.exec_module(module)
        return module

    try:
        sys.modules["scenarios"] = load("scenarios")
        yield load("runtime")
    finally:
        if old_scenarios is None:
            sys.modules.pop("scenarios", None)
        else:
            sys.modules["scenarios"] = old_scenarios
        for name in names:
            sys.modules.pop(name, None)


def _bounded(command, *, payload=None, timeout=15, max_bytes=MAX_RPC_BYTES):
    """Bound both elapsed time and captured bytes, including malicious stdout."""
    proc = subprocess.Popen(command, stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    selector = selectors.DefaultSelector()
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
    selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
    if payload is not None:
        os.set_blocking(proc.stdin.fileno(), False)
        selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
    remaining = memoryview(payload or b"")
    deadline = time.monotonic() + timeout
    try:
        while selector.get_map():
            wait = deadline - time.monotonic()
            if wait <= 0:
                raise TimeoutError("callback transport deadline exceeded")
            for key, _ in selector.select(min(wait, 0.2)):
                if key.data == "stdin":
                    if remaining:
                        try:
                            remaining = remaining[os.write(key.fileobj.fileno(), remaining[:65536]):]
                        except BrokenPipeError:
                            remaining = remaining[len(remaining):]
                    if not remaining:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        outputs[key.data].extend(block)
                        if sum(map(len, outputs.values())) > max_bytes:
                            raise ValueError("callback output limit exceeded")
        code = proc.wait(timeout=max(0.001, deadline - time.monotonic()))
        return code, bytes(outputs["stdout"]), bytes(outputs["stderr"])
    except BaseException:
        proc.kill()
        proc.wait(timeout=5)
        raise
    finally:
        selector.close()
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()


def parse_response(raw):
    try:
        result = json.loads(raw.decode("utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (ValueError, UnicodeError) as exc:
        raise CandidateError("invalid callback JSON") from exc
    if not isinstance(result, dict) or type(result.get("rpc_version")) is not int or result.get("rpc_version") != 1 or type(result.get("ok")) is not bool:
        raise CandidateError("invalid callback envelope")
    if result["ok"]:
        if set(result) != {"rpc_version", "ok", "result"}:
            raise CandidateError("invalid success fields")
        return result["result"]
    if set(result) != {"rpc_version", "ok", "error"} or not isinstance(result["error"], str):
        raise CandidateError("invalid error fields")
    raise CandidateError(result["error"][:1000])


class DockerInvoker:
    def __init__(self, candidate_dir, image=PINNED_IMAGE, callback_timeout=30, command_runner=_bounded):
        if not re.fullmatch(r"[A-Za-z0-9./:_-]+@sha256:[0-9a-f]{64}", image):
            raise IsolationError("image must be pinned by SHA256 digest")
        self.image = image
        self.callback_timeout = callback_timeout
        self.run = command_runner
        self.temp = tempfile.TemporaryDirectory(prefix="livemigrate-rpc-")
        self.snapshot = Path(self.temp.name) / "candidate"
        self.snapshot.mkdir(mode=0o755)
        source = Path(candidate_dir).resolve()
        try:
            for role in CALLS:
                path = source / (role + ".py")
                if path.is_symlink() or not path.is_file():
                    raise IsolationError("candidate requires regular " + role + ".py")
                if path.stat().st_size > MAX_RPC_BYTES:
                    raise IsolationError("candidate file too large: " + role)
                shutil.copyfile(path, self.snapshot / path.name)
                (self.snapshot / path.name).chmod(0o444)
        except BaseException:
            self.temp.cleanup()
            raise
        self.driver = Path(__file__).with_name("candidate_driver.py").resolve()
        self.containers = {}
        self.database_dir = None
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _destroy(self):
        for name in list(self.containers.values()):
            try:
                self.run(["docker", "rm", "-f", name], timeout=10, max_bytes=65536)
            except Exception:
                pass
        self.containers.clear()
        self.database_dir = None

    def close(self):
        self._destroy()
        self.temp.cleanup()

    def _container(self, database, readonly):
        directory = database.parent
        if self.database_dir is not None and self.database_dir != directory:
            self._destroy()
        if directory == self.snapshot or self.snapshot in directory.parents:
            raise IsolationError("database must be separate from candidate snapshot")
        # Mount no incidental host files, oracle code, expected state or logs.
        allowed = {database.name, database.name + "-wal", database.name + "-shm", database.name + "-journal"}
        if any(p.name not in allowed or p.is_symlink() or not p.is_file() for p in directory.iterdir()):
            raise IsolationError("database directory must contain only SQLite files")
        directory.chmod(0o777)
        for path in directory.iterdir():
            path.chmod(0o666)
        self.database_dir = directory
        key = "read" if readonly else "write"
        if key in self.containers:
            return self.containers[key]
        name = "livemigrate-" + uuid.uuid4().hex[:16]
        mode = "ro" if readonly else "rw"
        command = ["docker", "run", "-d", "--pull=never", "--name", name,
                   "--network=none", "--read-only", "--cap-drop=ALL",
                   # Per-driver hard RLIMIT_NPROC denies candidate descendants;
                   # leave headroom here for docker exec/tini process reaping.
                   "--security-opt=no-new-privileges", "--pids-limit=16", "--memory=256m",
                   "--cpus=1", "--user=65534:65534", "--init",
                   "--tmpfs=/tmp:rw,noexec,nosuid,size=64m,mode=1777",
                   "--mount", "type=bind,src=" + str(self.snapshot) + ",dst=/candidate,readonly",
                   "--mount", "type=bind,src=" + str(self.driver) + ",dst=/driver.py,readonly",
                   "--volume", str(directory) + ":/db:" + mode,
                   self.image, "python", "-I", "-B", "-c", "import time; time.sleep(86400)"]
        self.containers[key] = name
        try:
            code, stdout, stderr = self.run(command, timeout=30, max_bytes=65536)
        except Exception as exc:
            raise IsolationError("could not start isolated callback container") from exc
        if code != 0:
            raise IsolationError("container startup failed: " + stderr.decode(errors="replace")[:1000])
        return name

    def __call__(self, role, function, conn, *args):
        if role not in CALLS or function not in CALLS[role]:
            raise IsolationError("invalid callback dispatch")
        if conn.in_transaction:
            raise IsolationError("host transaction must close before isolated callback")
        files = conn.execute("PRAGMA database_list").fetchall()
        main = next((row[2] for row in files if row[1] == "main"), None)
        if not main:
            raise IsolationError("isolated callbacks require an on-disk SQLite database")
        supplied_database = Path(main)
        if supplied_database.is_symlink() or not supplied_database.is_file():
            raise IsolationError("invalid database file")
        database = supplied_database.resolve()
        name = self._container(database, role == "consumer")
        payload = json.dumps({"role": role, "function": function, "database": "/db/" + database.name,
                              "args": args}, allow_nan=False).encode()
        if len(payload) > MAX_RPC_BYTES:
            raise IsolationError("callback input limit exceeded")
        self.calls += 1
        try:
            code, stdout, stderr = self.run(["docker", "exec", "-i", name, "python", "-I", "-B", "/driver.py"],
                                          payload=payload, timeout=self.callback_timeout, max_bytes=MAX_RPC_BYTES)
        except (TimeoutError, subprocess.TimeoutExpired) as exc:
            self._destroy()  # docker-exec termination alone does not kill candidate children.
            raise CandidateTimeout(str(exc)) from exc
        except ValueError as exc:
            self._destroy()
            raise CandidateError(str(exc)) from exc
        except Exception as exc:
            self._destroy()
            raise IsolationError("callback transport failed") from exc
        if code != 0:
            raise CandidateError("callback process exited " + str(code) + ": " + stderr.decode(errors="replace")[:1000])
        return parse_response(stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--suite", choices=("public", "heldout", "all"), default="public")
    parser.add_argument("--image", default=PINNED_IMAGE)
    parser.add_argument("--callback-timeout", type=float, default=30)
    parser.add_argument("--task-root", type=Path, default=CORE_ROOT,
                        help="Trusted task folder containing runtime.py and scenarios.py; defaults to this family")
    args = parser.parse_args(argv)
    if args.callback_timeout <= 0 or args.callback_timeout > 60:
        parser.error("callback timeout must be between 0 and 60 seconds")
    # Only trusted task files are imported here; candidates remain in Docker.
    with task_runtime(args.task_root) as runtime:
        with DockerInvoker(args.candidate, args.image, args.callback_timeout) as invoke:
            output = runtime.run_suite(args.candidate, args.suite, invoke=invoke)
    print(json.dumps(output, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()

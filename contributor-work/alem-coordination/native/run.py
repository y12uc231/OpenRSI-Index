"""Single-container controller evaluation. No Docker client/socket is used here."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "controller"))
from launcher import (FrameProcess, SUITES, checked_worker_reply, digest,
                      incomplete_case, provenance, worker_error)
from feedback import public_feedback
from wire import decode
from sandbox import actor_root, copy_runtime


def source_inventory(source):
    names = set()
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            raise ValueError("source symlink is forbidden")
        if path.is_file():
            names.add(str(relative))
        elif not path.is_dir():
            raise ValueError("nonregular source entry")
    return names


def verified_inputs(candidate):
    # Verify exact declared file bytes/inventory directly; no git binary or mutable
    # Git metadata is needed inside the admitted environment.
    from launcher import regular, BASELINE, MAX_CANDIDATE
    spec = json.loads((BASELINE / "source-manifest.json").read_text())
    asset_spec = json.loads((BASELINE / "asset-manifest.json").read_text())
    source, assets = Path("/app"), Path("/assets")
    names = source_inventory(source)
    if names != set(spec["files"]):
        raise ValueError("source file inventory mismatch")
    hashes = {name: digest(regular(source, name)) for name in sorted(names)}
    if hashes != spec["files"]:
        raise ValueError("source digest mismatch")
    asset_hashes = {}
    for row in asset_spec["files"]:
        if not row["path"].startswith("assets/"):
            raise ValueError("asset prefix")
        name = row["path"].removeprefix("assets/")
        path = regular(assets, name)
        if path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]:
            raise ValueError("asset digest mismatch")
        asset_hashes[name] = row["sha256"]
    controller = regular(candidate, "controller.py")
    if controller.stat().st_size > MAX_CANDIDATE:
        raise ValueError("candidate exceeds1MiB")
    files = ["launcher.py","controller_driver.py","wire.py","engine.py","feedback.py","CONTRACT.md"]
    return {"source_revision":spec["revision"],"source_sha256":hashes,
            "asset_revision":asset_spec["revision"],"asset_sha256":asset_hashes,
            "candidate_sha256":digest(controller),
            "runner_sha256":{n:digest(ROOT.parent / "controller" / n) for n in files},
            "manifest_sha256":{n:digest(BASELINE / n) for n in ("source-manifest.json","asset-manifest.json")},
            "native_sha256":{p.name:digest(p) for p in sorted(ROOT.glob("*.py"))}}


def run(args):
    if not args.output.is_dir() or any(args.output.iterdir()):
        raise ValueError("output must be an existing empty directory")
    if args.output != Path("/results"):
        raise ValueError("trusted engine requires output at /results")
    if os.geteuid() != 0:
        raise RuntimeError("native route requires supported root verifier bootstrap")
    os.environ["PYTHONHASHSEED"] = "0"
    worlds = SUITES[args.suite][:1] if args.proof_first_world else SUITES[args.suite]
    start = time.monotonic()
    deadline = start + args.timeout
    launch = {"route": "native-chroot-uid-seccomp-v1", "suite": args.suite,
              "proof_first_world": args.proof_first_world, "operator_timeout_seconds": args.timeout,
              "python_version": sys.version, "milestones": [], "process_traffic": [], "llm_calls": 0}
    before, engine, failure, complete = None, None, None, False
    rows, workers = {}, []
    # Executable stdlib extensions must live on the regular container filesystem,
    # not a possibly noexec /tmp tmpfs. Actors still get private non-root /tmp.
    temporary = tempfile.TemporaryDirectory(prefix="alem-native-", dir="/var/lib")
    temporary_root = Path(temporary.name)
    snapshot = temporary_root / "candidate"
    world_root = None

    def remaining(limit):
        left = min(limit, deadline - time.monotonic())
        if left <= 0:
            raise TimeoutError("operator deadline")
        return left

    def close_workers():
        nonlocal world_root
        for worker in workers:
            try:
                worker.close()
            except Exception:
                launch["cleanup_incomplete"] = True
            launch["process_traffic"].append(worker.stats())
        workers.clear()
        if world_root is not None:
            shutil.rmtree(world_root)
            world_root = None

    try:
        before = verified_inputs(args.candidate)
        launch["hashes_before"] = before
        snapshot.mkdir()
        shutil.copyfile(args.candidate / "controller.py", snapshot / "controller.py")
        (snapshot / "controller.py").chmod(0o444)
        if digest(snapshot / "controller.py") != before["candidate_sha256"]:
            raise ValueError("candidate changed during snapshot")
        template = temporary_root / "template"
        copy_runtime(template)
        runtime_files = {str(p.relative_to(template)):digest(p) for p in sorted(template.rglob("*")) if p.is_file()}
        launch["actor_runtime"] = {"file_count":len(runtime_files), "tree_sha256":hashlib.sha256(json.dumps(runtime_files,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
        command = [sys.executable, "-B", str(ROOT / "engine_entry.py"), "--suite", args.suite]
        if args.proof_first_world:
            command.append("--proof-first-world")
        engine = FrameProcess(command, args.output / "engine.stderr.txt")
        current_world = None
        expected = iter(worlds)
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
                world_root = temporary_root / "actors"
                world_root.mkdir()
                try:
                    for actor in range(3):
                        command = actor_root(template, world_root / str(actor), snapshot, actor)
                        worker = FrameProcess(command, args.output / f"world-{current_world}-actor-{actor}.stderr.txt")
                        workers.append(worker)
                        worker.send({"kind":"initialize", "agent_id":actor,"schema":message["schema"]}, timeout=remaining(30))
                    for worker in workers:
                        response = checked_worker_reply(worker.recv(timeout=remaining(30)), initializing=True)
                        error = error or response.get("error")
                except Exception as exc:
                    error = worker_error(exc)
                engine.send({"error":error} if error else {"ready":True}, timeout=remaining(30))
            elif kind == "actions":
                packets = message.get("packets")
                if current_world is None or not isinstance(packets, list) or len(packets) != 3 or len(workers) != 3:
                    raise ValueError("engine action sequence")
                actions, error = [], None
                try:
                    for worker, packet in zip(workers, packets):
                        worker.send({"kind":"act","local":packet}, timeout=remaining(30))
                    for worker in workers:
                        response = checked_worker_reply(worker.recv(timeout=remaining(30)))
                        error = error or response.get("error")
                        if "action" in response:
                            actions.append(response["action"])
                except Exception as exc:
                    error = worker_error(exc)
                engine.send({"error":error} if error else {"actions":actions}, timeout=remaining(30))
            elif kind == "world_result":
                if message.get("world_id") != current_world or current_world in rows or message.get("result",{}).get("world_id") != current_world:
                    raise ValueError("engine result sequence")
                rows[current_world] = message["result"]
                close_workers()
                current_world = None
            elif kind == "done":
                if len(rows) != len(worlds) or message.get("total") != len(rows):
                    raise ValueError("incomplete engine suite")
                if engine.proc.wait(timeout=remaining(30)) != 0:
                    raise RuntimeError("engine nonzero exit")
                complete = True
                break
            else:
                raise ValueError("unknown engine message")
    except BaseException as exc:
        failure = "operator_timeout" if isinstance(exc, TimeoutError) else "engine_failure"
        launch["error"] = {"code":failure,"error_type":type(exc).__name__,"message":str(exc)}
    finally:
        try:
            close_workers()
        except Exception:
            launch["cleanup_incomplete"] = True
        if engine is not None:
            try:
                engine.close()
                launch["process_traffic"].append(engine.stats())
            except Exception:
                launch["cleanup_incomplete"] = True
        temporary.cleanup()
        try:
            after = verified_inputs(args.candidate)
            launch["hashes_after"] = after
            launch["source_candidate_unchanged"] = before is not None and before == after
        except Exception as exc:
            launch["source_candidate_unchanged"] = False
            launch["verification_error_type"] = type(exc).__name__
        if not launch["source_candidate_unchanged"]:
            failure = failure or "source_changed"
        if launch.get("cleanup_incomplete"):
            failure = failure or "engine_failure"
        result = {}
        if complete and not failure:
            try:
                result = decode((args.output / "engine-result.private.json").read_bytes())
                if result.get("world_ids") != worlds or result.get("cases") != [rows[w] for w in worlds] or result.get("total") != len(rows):
                    raise ValueError("engine result differs from reported worlds")
                if result.get("status") not in ("scored","unscored"):
                    raise ValueError("engine status")
            except Exception:
                failure = "engine_failure"
        if not complete:
            failure = failure or "incomplete"
        if failure:
            result = {"schema_version":1,"status":"unscored","suite":args.suite,
                      "world_ids":worlds,"total":len(worlds),"primary_score":None,"metrics_mean":{},
                      "cases":[rows.get(w,incomplete_case(w,failure)) for w in worlds],"infrastructure_diagnostic":failure}
            result["scored"] = sum(c["status"] == "scored" for c in result["cases"])
        launch["wall_seconds"] = time.monotonic() - start
        result["host_provenance"] = {key:launch[key] for key in ("route","python_version","proof_first_world","source_candidate_unchanged","operator_timeout_seconds","wall_seconds","llm_calls")}
        result["host_provenance"]["hashes"] = before
        result["host_provenance"]["actor_runtime"] = launch.get("actor_runtime")
        result["validation_scope"] = "first-world-deployment-proof" if args.proof_first_world else "fixed-full-suite"
        result["infrastructure_affected"] = bool(failure or launch.get("cleanup_incomplete"))
        result["provenance_verified"] = bool(complete and not failure and launch["source_candidate_unchanged"])
        (args.output / "result.json").write_text(json.dumps(result, indent=2,sort_keys=True,allow_nan=False)+"\n")
        (args.output / "launch.private.json").write_text(json.dumps(launch,indent=2,sort_keys=True,allow_nan=False)+"\n")
        feedback = public_feedback(result)
        feedback["validation_scope"] = result["validation_scope"]
        (args.output / "feedback.json").write_text(json.dumps(feedback,indent=2,sort_keys=True,allow_nan=False)+"\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--suite", choices=SUITES, required=True)
    parser.add_argument("--output", type=Path, default=Path("/results"))
    parser.add_argument("--timeout", type=float, default=10800)
    parser.add_argument("--proof-first-world", action="store_true")
    args = parser.parse_args()
    args.candidate = args.candidate.resolve()
    args.output = args.output.resolve()
    if not 0 < args.timeout <= 172800:
        parser.error("timeout must be positive and at most48hours")
    def interrupted(signum, frame):
        raise InterruptedError("operator signal")
    signal.signal(signal.SIGTERM, interrupted)
    result = run(args)
    print(json.dumps(public_feedback(result),sort_keys=True,allow_nan=False))
    if not result["provenance_verified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

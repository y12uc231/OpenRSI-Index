"""Stage and run one candidate using the audited, ordinary-container native route.

CLI is prepare-only unless --run is explicit. evaluate(...) is the corresponding
explicit execution API. No downloads, image builds, candidate imports, inference,
or retries are performed. Each output directory is new and contains private logs.

The optional transfer suite is an independent-paper extension, not an original
OpenRSI/pilot result. Only staged suite dispatch/world literals change; the patch,
original hashes, effective hashes, resource limits, and every world are retained.
"""
import argparse
import difflib
import fcntl
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import uuid


DEFAULT_IMAGE = "sha256:9282bdeb7b8debc675830cf464028cba51b9a7b83afd8c1f4c098f67edd73176"
SOURCE_REVISION = "14d412e5ee961f9c43d6ce92ee05fee9cd1efc5e"
ASSET_REVISION = "9493179ea5e86cd625add66c0f88e23f04f928b5"
SUITES = {"dev": list(range(20000, 20004)), "evaluation": list(range(9999, 10019)),
          "transfer": list(range(30000, 30020))}
NATIVE = ("run.py", "sandbox.py", "actor_bootstrap.py", "engine_entry.py", "engine.py",
          "probe.py", "runtime_support.py", "README.md", "ENGINE.patch")
CONTROLLER = ("launcher.py", "controller_driver.py", "wire.py", "feedback.py", "engine.py",
              "CONTRACT.md", "reference/controller.py")
ENV = {"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "JAX_PLATFORM_NAME": "cpu",
       "WANDB_MODE": "disabled", "MPLCONFIGDIR": "/tmp/matplotlib",
       "XDG_CACHE_HOME": "/tmp/cache", "OMP_NUM_THREADS": "4"}
RESOURCES = {"cpus": 4, "memory_gib": 16, "pids_limit": 256, "network": "none",
             "gpus": 0, "cap_drop": ["NET_RAW"], "extra_capabilities": []}
METRIC = "Team/coord_reward_pct_of_max"
MAX_CANDIDATE = 1024 * 1024
MAX_RESULT = 16 * 1024 * 1024


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read_json(path):
    def reject_constant(value):
        raise ValueError("nonfinite JSON constant")
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_constant)


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def regular(root, name):
    """Only a canonical relative path with regular, non-symlink components."""
    root, name = Path(root), PurePosixPath(name)
    if name.is_absolute() or not name.parts or any(p in (".", "..") for p in name.parts):
        raise ValueError("invalid relative input path")
    current = root
    if root.is_symlink() or not root.is_dir():
        raise ValueError("input root must be a real directory")
    for part in name.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink input forbidden")
    if not current.is_file():
        raise ValueError("input must be a regular file")
    return current


def copy_regular(source, destination, expected=None):
    if source.is_symlink() or not source.is_file():
        raise ValueError("nonregular copy input")
    before = digest(source)
    if expected is not None and before != expected:
        raise ValueError("input hash mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if digest(destination) != before or digest(source) != before:
        raise ValueError("input changed during copy")
    destination.chmod(0o444)


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError("nonregular staged entry")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = digest(path)
    return result


def transfer_adapter(stage):
    """Fail closed on drift; never modify the original trusted task files."""
    changes = {
        "run.py": [("FrameProcess, SUITES = launcher.FrameProcess, launcher.SUITES",
                    "FrameProcess, SUITES = launcher.FrameProcess, {**launcher.SUITES, 'transfer': list(range(30000, 30020))}")],
        "engine.py": [("choices=('dev','evaluation')", "choices=('dev','evaluation','transfer')"),
                      ("worlds=list(range(20000,20004)) if args.suite=='dev' else list(range(9999,10019))",
                       "worlds={'dev':list(range(20000,20004)), 'evaluation':list(range(9999,10019)), 'transfer':list(range(30000,30020))}[args.suite]")],
    }
    patches, records = [], {}
    for name, replacements in changes.items():
        path = stage / "task/native" / name
        old = path.read_text(encoding="utf-8")
        new = old
        for original, replacement in replacements:
            if new.count(original) != 1:
                raise ValueError("transfer adapter source mismatch")
            new = new.replace(original, replacement)
        records[name] = {"original_sha256": digest(path),
                         "effective_sha256": hashlib.sha256(new.encode()).hexdigest()}
        path.chmod(0o644)
        path.write_text(new, encoding="utf-8")
        path.chmod(0o444)
        patches.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                          fromfile="original/native/" + name, tofile="staged/native/" + name))
    return "".join(patches), records


def prepare(task, source, assets, image, candidate, suite, output, *, timeout=10800):
    """Prepare a new directory without contacting Docker or executing source."""
    task, source, assets, candidate, output = map(Path, (task, source, assets, candidate, output))
    if suite not in SUITES or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 172800:
        raise ValueError("invalid suite or operator timeout")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("image must be an immutable local sha256 image ID")
    # A file or a directory may be supplied; only controller.py crosses the boundary.
    candidate_file = regular(candidate, "controller.py") if candidate.is_dir() else regular(candidate.parent, candidate.name)
    if candidate_file.stat().st_size > MAX_CANDIDATE:
        raise ValueError("candidate exceeds 1MiB")
    spec = read_json(regular(task, "baseline/source-manifest.json"))
    asset_spec = read_json(regular(task, "baseline/asset-manifest.json"))
    if spec.get("revision") != SOURCE_REVISION or asset_spec.get("revision") != ASSET_REVISION:
        raise ValueError("upstream revision differs from frozen baseline")
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    stage = output / "stage"
    for name, expected in sorted(spec["files"].items()):
        copy_regular(regular(source, name), stage / "app" / name, expected)
    asset_names = set()
    for row in asset_spec["files"]:
        if not row["path"].startswith("assets/"):
            raise ValueError("asset prefix")
        name = row["path"][7:]
        path = regular(assets, name)
        if name in asset_names or path.stat().st_size != row["bytes"]:
            raise ValueError("duplicate asset or asset size mismatch")
        asset_names.add(name)
        copy_regular(path, stage / "assets" / name, row["sha256"])
    for name in ("source-manifest.json", "asset-manifest.json"):
        copy_regular(regular(task, "baseline/" + name), stage / "task/baseline" / name)
    for name in CONTROLLER:
        copy_regular(regular(task, "controller/" + name), stage / "task/controller" / name)
    for name in NATIVE:
        copy_regular(regular(task, "native/" + name), stage / "task/native" / name)
    copy_regular(regular(task, "TASK_DESIGN.md"), stage / "task/TASK_DESIGN.md")
    copy_regular(candidate_file, stage / "candidate/controller.py")
    original_files = inventory(stage)
    patch, adaptations = transfer_adapter(stage) if suite == "transfer" else ("", {})
    (output / "transfer.patch").write_text(patch, encoding="utf-8")
    manifest = {"schema_version": 1, "image": image, "env": ENV, "resources": RESOURCES,
                "suite": suite, "world_ids": SUITES[suite], "operator_timeout_seconds": timeout,
                "source_revision": spec["revision"], "asset_revision": asset_spec["revision"],
                "source_file_count": len(spec["files"]), "asset_file_count": len(asset_names),
                "candidate_sha256": digest(stage / "candidate/controller.py"),
                "original_files": original_files, "files": inventory(stage), "adaptations": adaptations,
                "transfer_patch_sha256": digest(output / "transfer.patch"),
                "wrapper_sha256": digest(Path(__file__)), "automatic_retries": 0, "llm_calls": 0,
                "scientific_scope": ("independent-paper new-world transfer; not the original pilot evaluation; native scope text is inherited"
                                     if suite == "transfer" else "unchanged original controller suite"),
                "input_mounts_readonly": True, "expected_outcomes_mounted": False}
    dump(output / "manifest.json", manifest)
    return manifest


def docker_command(output, manifest, name):
    command = ["docker", "run", "--pull=never", "--name", name, "--network", "none",
               "--cpus", "4", "--memory", "16g", "--pids-limit", "256", "--cap-drop", "NET_RAW", "--user", "0"]
    for key, value in ENV.items():
        command += ["--env", key + "=" + value]
    for item in ("app", "assets", "task", "candidate"):
        path = str(output / "stage" / item)
        if "," in path or "\n" in path:
            raise ValueError("Docker bind path contains unsupported delimiter")
        command += ["--mount", "type=bind,src=" + path + ",dst=/" + item + ",readonly"]
    command += ["--mount", "type=bind,src=" + str(output / "output") + ",dst=/results",
                manifest["image"], "python", "-I", "-B", "/task/native/run.py",
                "--candidate", "/candidate", "--suite", manifest["suite"], "--output", "/results",
                "--timeout", str(manifest["operator_timeout_seconds"])]
    return command


def expected_hashes(manifest):
    files = manifest["files"]
    subset = lambda prefix: {key[len(prefix):]: value for key, value in files.items() if key.startswith(prefix)}
    runner = {name: files["task/controller/" + name] for name in CONTROLLER if name != "reference/controller.py"}
    return {"source_revision": manifest["source_revision"], "source_sha256": subset("app/"),
            "asset_revision": manifest["asset_revision"], "asset_sha256": subset("assets/"),
            "candidate_sha256": manifest["candidate_sha256"], "runner_sha256": runner,
            "manifest_sha256": subset("task/baseline/"),
            "native_sha256": {name: value for name, value in subset("task/native/").items() if name.endswith(".py")}}


def validate_result(result, manifest):
    """Recompute the complete-suite denominator; never average just valid rows."""
    problems = []
    worlds, cases = manifest["world_ids"], result.get("cases", [])
    count = len(worlds)
    if (result.get("suite") != manifest["suite"] or result.get("world_ids") != worlds
            or type(result.get("total")) is not int or result["total"] != count
            or not isinstance(cases, list) or len(cases) != count
            or any(not isinstance(c, dict) for c in cases)
            or [c.get("world_id") for c in cases] != worlds):
        return ["world_inventory_mismatch"], None
    number = lambda n: type(n) in (int, float) and math.isfinite(n)
    close = lambda a, b: number(a) and number(b) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    scores, scored = [], 0
    for case in cases:
        if case.get("status") == "scored":
            scored += 1
            score = case.get("metrics", {}).get(METRIC)
            if not number(score) or not 0 <= score <= 1 or not close(score, case.get("score")):
                problems.append("invalid_world_score")
            else:
                scores.append(score)
        elif case.get("status") not in ("candidate_invalid", "infrastructure_or_incomplete"):
            problems.append("invalid_world_status")
        elif case.get("score") is not None or case.get("metrics") not in ({}, None):
            problems.append("invalid_world_has_score")
        if case.get("status") == "infrastructure_or_incomplete":
            problems.append("world_infrastructure_or_incomplete")
    if type(result.get("scored")) is not int or result["scored"] != scored:
        problems.append("scored_count_mismatch")
    mean = sum(scores) / count if len(scores) == count else None
    if mean is not None:
        if (result.get("status") != "scored" or not close(mean, result.get("primary_score"))
                or not close(mean, (result.get("metrics_mean") or {}).get(METRIC))):
            problems.append("primary_mean_mismatch")
    elif result.get("status") != "unscored" or result.get("primary_score") is not None:
        problems.append("partial_suite_has_primary_score")
    provenance = result.get("host_provenance") or {}
    if provenance.get("hashes") != expected_hashes(manifest):
        problems.append("artifact_hash_mismatch")
    if (provenance.get("proof_first_world") is not False or provenance.get("source_candidate_unchanged") is not True
            or result.get("validation_scope") != "fixed-full-suite"):
        problems.append("native_run_scope_mismatch")
    if result.get("provenance_verified") is not True or result.get("infrastructure_affected") is not False:
        problems.append("native_provenance_or_infrastructure_failure")
    return sorted(set(problems)), mean


def execute_prepared(output, evaluation_lock):
    """Run a previously prepared directory exactly once; no automatic retries."""
    output, evaluation_lock = Path(output).resolve(), Path(evaluation_lock)
    manifest = read_json(output / "manifest.json")
    manifest_digest = digest(output / "manifest.json")
    if (manifest["files"] != inventory(output / "stage") or manifest["wrapper_sha256"] != digest(Path(__file__))
            or manifest["transfer_patch_sha256"] != digest(output / "transfer.patch")):
        raise ValueError("prepared inputs changed")
    (output / "output").mkdir(exist_ok=False)
    # flock is shared with all other study evaluators. The queue time is not rollout time.
    evaluation_lock.parent.mkdir(parents=True, exist_ok=True)
    name = "alem-paper-" + uuid.uuid4().hex
    command = docker_command(output, manifest, name)
    operator = {"schema_version": 1, "command": command, "resources": RESOURCES,
                "returncode": None, "automatic_retries": 0, "llm_calls": 0, "error_type": None}
    begin = time.monotonic()
    try:
        with evaluation_lock.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            operator["queue_seconds"] = time.monotonic() - begin
            start = time.monotonic()
            try:
                inspected = subprocess.run(["docker", "image", "inspect", manifest["image"]], capture_output=True, text=True, timeout=30, check=True)
                image = json.loads(inspected.stdout)[0]
                if image["Id"] != manifest["image"]:
                    raise ValueError("resolved image identity mismatch")
                operator["image"] = {k: image.get(k) for k in ("Id", "Architecture", "Os")}
                # Keep all raw output private and off the host's memory critical path.
                with (output / "docker.stdout.private.txt").open("wb") as stdout, (output / "docker.stderr.private.txt").open("wb") as stderr:
                    result = subprocess.run(command, stdout=stdout, stderr=stderr,
                                            timeout=manifest["operator_timeout_seconds"] + 60)
                    operator["returncode"] = result.returncode
            except Exception as exc:
                operator["error_type"] = type(exc).__name__
            finally:
                operator["seconds"] = time.monotonic() - start
                try:
                    state = subprocess.run(["docker", "inspect", name], capture_output=True, text=True, timeout=30)
                    operator["container_state"] = json.loads(state.stdout)[0]["State"] if state.returncode == 0 else None
                except Exception as exc:
                    operator["inspect_error_type"] = type(exc).__name__
                try:
                    cleanup = subprocess.run(["docker", "rm", "--force", name], capture_output=True, text=True, timeout=30)
                    # A missing container is expected if image inspection failed before run.
                    operator["cleanup_ok"] = cleanup.returncode == 0 or (operator.get("image") is None and operator.get("container_state") is None)
                except Exception as exc:
                    operator["cleanup_ok"] = False
                    operator["cleanup_error_type"] = type(exc).__name__
    except Exception as exc:
        operator["error_type"] = type(exc).__name__
        operator["cleanup_ok"] = False
    finally:
        dump(output / "operator.private.json", operator)
    problems, result, mean, result_digest, feedback_digest = [], None, None, None, None
    try:
        if (manifest["files"] != inventory(output / "stage") or digest(output / "manifest.json") != manifest_digest
                or digest(output / "transfer.patch") != manifest["transfer_patch_sha256"] or digest(Path(__file__)) != manifest["wrapper_sha256"]):
            problems.append("prepared_inputs_changed")
    except (OSError, ValueError):
        problems.append("prepared_inputs_unreadable")
    try:
        path = regular(output / "output", "result.json")
        if path.stat().st_size > MAX_RESULT:
            raise ValueError("result exceeds bound")
        result = read_json(path)
        if not isinstance(result, dict):
            result = None
            raise ValueError("result must be object")
        result_problems, mean = validate_result(result, manifest)
        problems += result_problems
        result_digest = digest(path)
        feedback_path = regular(output / "output", "feedback.json")
        if feedback_path.stat().st_size > MAX_RESULT or not isinstance(read_json(feedback_path), dict):
            raise ValueError("invalid feedback artifact")
        feedback_digest = digest(feedback_path)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        problems.append("result_missing_or_invalid")
    if operator["returncode"] != 0 or operator["error_type"] or not operator.get("cleanup_ok"):
        problems.append("operator_failure")
    state = operator.get("container_state")
    if not isinstance(state, dict) or state.get("Running") is not False or state.get("OOMKilled") is not False or state.get("ExitCode") != 0:
        problems.append("container_exit_unverified")
    valid = not problems
    cases = (result or {}).get("cases", [])
    counts = {status: sum(isinstance(c, dict) and c.get("status") == status for c in cases)
              for status in ("scored", "candidate_invalid", "infrastructure_or_incomplete")} if isinstance(cases, list) else {}
    summary = {"schema_version": 1, "operator_status": "completed" if valid else "infrastructure_or_incomplete",
               "status": result.get("status") if valid else "unscored", "suite": manifest["suite"],
               "world_ids": manifest["world_ids"], "total": len(manifest["world_ids"]),
               "scored": counts.get("scored", 0),
               "primary_score": mean if valid else None, "provenance_verified": valid,
               "diagnostics": sorted(set(problems)), "candidate_sha256": manifest["candidate_sha256"],
               "manifest_sha256": manifest_digest, "scientific_scope": manifest["scientific_scope"],
               "result_sha256": result_digest, "feedback_sha256": feedback_digest,
               "validity_counts": counts,
               "automatic_retries": 0, "llm_calls": 0, "resources": RESOURCES,
               "seconds": operator.get("seconds"), "queue_seconds": operator.get("queue_seconds"),
               "returncode": operator["returncode"], "result_path": str(output / "output/result.json"),
               "feedback_path": str(output / "output/feedback.json"), "manifest_path": str(output / "manifest.json"),
               "operator_path": str(output / "operator.private.json")}
    dump(output / "evaluation.json", summary)
    return summary


def evaluate(task, source, assets, image, candidate, suite, output, evaluation_lock, *, timeout=10800):
    """Explicit one-run API. Caller authorizes computation by calling this function."""
    prepare(task, source, assets, image, candidate, suite, output, timeout=timeout)
    return execute_prepared(output, evaluation_lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("task", "source", "assets", "candidate", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--suite", choices=SUITES, required=True)
    parser.add_argument("--evaluation-lock", type=Path)
    parser.add_argument("--timeout", type=float, default=10800)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.run and args.evaluation_lock is None:
        parser.error("--run requires --evaluation-lock shared with the study")
    call = {key: getattr(args, key) for key in ("task", "source", "assets", "image", "candidate", "suite", "output", "timeout")}
    if args.run:
        summary = evaluate(**call, evaluation_lock=args.evaluation_lock)
    else:
        manifest = prepare(**call)
        summary = {"executed": False, "manifest_path": str(args.output / "manifest.json"),
                   "manifest_sha256": digest(args.output / "manifest.json"), "candidate_sha256": manifest["candidate_sha256"],
                   "suite": args.suite, "world_ids": manifest["world_ids"]}
    print(json.dumps(summary, sort_keys=True, allow_nan=False))
    if args.run and summary["operator_status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

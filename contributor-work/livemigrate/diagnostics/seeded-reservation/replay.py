"""Replay one sealed schedule with candidate callbacks restricted to Docker."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys
import time

from package_integrity import ROOT, digest, trusted_modules, verify


def candidate_hashes(directory):
    result = {}
    for role in ("db", "api", "consumer"):
        path = directory / (role + ".py")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("candidate requires bounded regular role source files")
        result[role] = digest(path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--index", type=int, choices=range(20), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 11) or not hasattr(sqlite3.Connection, "setlimit"):
        parser.error("host Python >=3.11 with sqlite3.Connection.setlimit is required")
    candidate, output = args.candidate.resolve(), args.output.resolve()
    if output.exists():
        parser.error("output already exists; choose a new record, never overwrite")
    provenance = verify()
    before_manifest = (ROOT / "PACKAGE-SHA256.json").read_bytes()
    expected_candidate = candidate_hashes(candidate)
    modules = trusted_modules()
    runtime, scenarios, isolated = (modules[name] for name in ("runtime", "scenarios", "isolated"))
    start = time.monotonic()
    try:
        # The frozen invoker snapshots only role source and the public immutable
        # helper. It never mounts the oracle, another store, or host credentials.
        with isolated.MultiStoreInvoker(candidate, legacy_helper=ROOT / "task/reference/immutable_v1.py") as invoke:
            result = runtime.execute(candidate, scenarios.make_case(args.index), invoke=invoke)
    except Exception as exc:
        result = {"status": "infrastructure_or_incomplete", "passed": False,
                  "score": None, "error_type": type(exc).__name__}
    verify()
    if (ROOT / "PACKAGE-SHA256.json").read_bytes() != before_manifest or candidate_hashes(candidate) != expected_candidate:
        raise ValueError("package or candidate changed during replay; result unscored")
    record = {"scope": "exploratory seeded schedule coverage; original model scores unchanged",
              "index": args.index, "split": "calibration" if args.index < 4 else "evaluation",
              "seal_sha256": provenance["original_seal_sha256"],
              "package_manifest_sha256": hashlib.sha256(before_manifest).hexdigest(),
              "runner_kind": "portable_public_packaging_v1", "runner_sha256": digest(Path(__file__)),
              "original_runner_sha256": provenance["original_replay_runner_sha256"],
              "candidate_sha256": expected_candidate, "source_verified": True,
              "model_calls": 0, "seconds": time.monotonic() - start,
              "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
              "docker_image": isolated.PINNED_IMAGE, "result": result}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the destination atomically only after the entire record is ready.
    with output.open("x") as handle:
        handle.write(json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"index": args.index, "status": result["status"],
                      "passed": result["passed"], "seconds": round(record["seconds"], 3)}))


if __name__ == "__main__":
    main()

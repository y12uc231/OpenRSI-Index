"""Integrity checks for the portable package; never loads candidate source."""
from pathlib import Path
import difflib
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def verify():
    manifest = read_json(ROOT / "PACKAGE-SHA256.json")
    present_source = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py")}
    if present_source != {name for name in manifest["files"] if name.endswith(".py")}:
        raise ValueError("package source inventory differs from manifest")
    for name, expected in manifest["files"].items():
        path = ROOT / name
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink() or digest(path) != expected:
            raise ValueError("package file mismatch: " + name)
    provenance = read_json(ROOT / "PROVENANCE.json")
    if digest(ROOT / "provenance/original_replay.py") != provenance["original_replay_runner_sha256"]:
        raise ValueError("archived replay wrapper mismatch")
    seal = provenance["original_seal_metadata"]
    for name, record in provenance["exact_copies"].items():
        expected = (seal["source_sha256"] | seal["validation_sha256"])[record["original_path"]]
        if digest(ROOT / name) != expected or record["sha256"] != expected:
            raise ValueError("sealed copy mismatch: " + name)
    original = (ROOT / "frozen/runtime.py").read_text()
    modified = (ROOT / "task/runtime.py").read_text()
    patch = "".join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                    fromfile="frozen/runtime.py", tofile="diagnostic/task/runtime.py"))
    if patch != (ROOT / "RUNTIME.patch").read_text():
        raise ValueError("runtime differs from published patch")
    upstream = read_json(ROOT / "upstream-source-hashes.json")["sha256"]
    for name, expected in upstream.items():
        if name == "families/reservation/runtime.py":
            public = "frozen/runtime.py"
        elif name == "families/reservation/scenarios.py":
            public = "task/base_scenarios.py"
        elif name.startswith("families/reservation/"):
            public = "task/" + name.removeprefix("families/reservation/")
        else:
            public = "transport/" + name
        if digest(ROOT / public) != expected:
            raise ValueError("frozen source mismatch: " + public)
    return provenance


def trusted_modules():
    """CLI-only exact-path loader. Candidate paths are never import paths."""
    modules = {}
    for name, relative in (("base_scenarios", "task/base_scenarios.py"),
                           ("schedule_policy", "task/schedule_policy.py"),
                           ("scenarios", "task/scenarios.py"),
                           ("history", "task/history.py"),
                           ("runtime", "task/runtime.py"),
                           ("isolated", "transport/isolated.py")):
        spec = importlib.util.spec_from_file_location(name, ROOT / relative)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


def validate_published():
    provenance = verify()
    modules = trusted_modules()
    generated = modules["scenarios"].suite("all")
    seeds = read_json(ROOT / "seed-manifest.json")
    if generated != seeds["cases"] or len(generated) != 20:
        raise ValueError("generated cases do not match sealed seed manifest")
    host = read_json(ROOT / "results/trusted-controls.json")
    docker = read_json(ROOT / "results/docker-reference-calibration-00.json")
    controls = {"reference", "alternate_wire_schema", "drain_before_handoff", "deferred_move", "early_ack"}
    expected = {(control, i) for control in controls for i in range(20)}
    rows = host["cases"]
    actual = {(row["control"], row["index"]) for row in rows}
    if actual != expected or len(rows) != 100 or not host["source_unchanged"]:
        raise ValueError("trusted validation grid incomplete")
    for row in rows + docker["cases"]:
        result = row["result"]
        if result["status"] != "scored" or result["score"] != 1 or result["passed"] is not True:
            raise ValueError("published trusted result is not a pass")
        if result["schedule_audit"]["config"] != generated[row["index"]]["schedule_audit"]:
            raise ValueError("published result seed mismatch")
    reference = next(row for row in rows if row["control"] == "reference" and row["index"] == 0)
    if len(docker["cases"]) != 1 or docker["cases"][0]["result"] != reference["result"] or not docker["source_unchanged"]:
        raise ValueError("Docker validation differs from host reference")
    return {"status": "verified", "original_seal_sha256": provenance["original_seal_sha256"],
            "package_files": len(read_json(ROOT / "PACKAGE-SHA256.json")["files"]),
            "exact_sealed_copies": len(provenance["exact_copies"]), "generated_cases": 20,
            "historical_trusted_host_passed": 100, "historical_trusted_docker_passed": 1,
            "candidate_executions": 0, "model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(validate_published(), indent=2, sort_keys=True))

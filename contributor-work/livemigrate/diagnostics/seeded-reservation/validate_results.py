"""Validate completed replay records without executing candidate source."""
import argparse
import json
from pathlib import Path
import re

from package_integrity import ROOT, digest, read_json, verify


def validate(directory, expected_candidate, allow_incomplete=False):
    provenance = verify()
    if set(expected_candidate) != {"db", "api", "consumer"}:
        raise ValueError("candidate manifest must contain exactly db/api/consumer hashes")
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
           for value in expected_candidate.values()):
        raise ValueError("candidate hashes must be lowercase SHA256 digests")
    cases = read_json(ROOT / "seed-manifest.json")["cases"]
    accepted_runners = {provenance["original_replay_runner_sha256"], digest(ROOT / "replay.py")}
    records = []
    seen = set()
    for path in sorted(Path(directory).glob("*.json")):
        record = read_json(path)
        index = record.get("index")
        if type(index) is not int or index not in range(20) or index in seen:
            raise ValueError("invalid or repeated case index")
        seen.add(index)
        if (record.get("candidate_sha256") != expected_candidate
                or record.get("seal_sha256") != provenance["original_seal_sha256"]
                or record.get("runner_sha256") not in accepted_runners
                or record.get("source_verified") is not True
                or type(record.get("model_calls")) is not int or record.get("model_calls") != 0
                or record.get("split") != ("calibration" if index < 4 else "evaluation")):
            raise ValueError("replay provenance mismatch")
        if record["runner_sha256"] == digest(ROOT / "replay.py"):
            if record.get("package_manifest_sha256") != digest(ROOT / "PACKAGE-SHA256.json"):
                raise ValueError("portable replay package manifest mismatch")
        outcome = record["result"]
        status, passed, score = outcome.get("status"), outcome.get("passed"), outcome.get("score")
        if type(passed) is not bool:
            raise ValueError("invalid passed flag")
        if status == "scored":
            if type(score) not in (int, float) or score not in (0, 1) or passed != bool(score):
                raise ValueError("inconsistent scored outcome")
        elif status not in ("candidate_invalid", "infrastructure_or_incomplete", "unscored_audit_bound", "unscored_checker_bound") or score is not None or passed:
            raise ValueError("invalid unscored outcome")
        if "schedule_audit" in outcome:
            if outcome["schedule_audit"]["config"] != cases[index]["schedule_audit"]:
                raise ValueError("record uses a different seeded case")
        elif status == "scored":
            raise ValueError("scored record missing schedule diagnostics")
        records.append(record)
    missing = sorted(set(range(20)) - seen)
    if missing and not allow_incomplete:
        raise ValueError("incomplete pack; missing indices: " + str(missing))
    def group(rows):
        return {"records": len(rows), "passed": sum(r["result"]["passed"] for r in rows),
                "scored": sum(r["result"]["status"] == "scored" for r in rows),
                "unscored": sum(r["result"]["status"] != "scored" for r in rows),
                "output_loss_exercised": sum(r["result"].get("schedule_audit", {}).get("output_trigger") is not None for r in rows),
                "added_link_deferral_exercised": sum(r["result"].get("schedule_audit", {}).get("additional_link_deferrals", 0) > 0 for r in rows)}
    return {"status": "incomplete" if missing else "complete", "missing_indices": missing,
            "original_scores_unchanged": True, "candidate_sha256": expected_candidate,
            "calibration": group([r for r in records if r["index"] < 4]),
            "evaluation": group([r for r in records if r["index"] >= 4]),
            "all": group(records), "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True, help="directory containing only per-index replay JSON records")
    parser.add_argument("--candidate-hashes", type=Path, required=True, help="existing db/api/consumer SHA256 object")
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate(args.results, read_json(args.candidate_hashes), args.allow_incomplete), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

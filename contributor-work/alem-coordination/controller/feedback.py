"""Allowlisted aggregate-only feedback; never returns per-world records/logs."""
import argparse
import collections
import json
import math
from pathlib import Path

METRICS = {"Team/" + name for name in (
    "reward_pct_of_max", "normal_reward_pct_of_max", "coord_reward_pct_of_max",
    "soft_coord_reward_pct_of_max", "sync_hard_coord_reward_pct_of_max",
    "handover_coord_reward_pct_of_max", "construction_coord_reward_pct_of_max")}
STATUSES = {"scored", "candidate_invalid", "infrastructure_or_incomplete"}
ERROR_TYPES = {"SyntaxError", "TypeError", "KeyError", "ValueError", "NameError", "AttributeError",
               "ImportError", "IndexError", "ZeroDivisionError", "MemoryError"}
CODES = {"candidate_import", "candidate_initialize", "candidate_act", "candidate_output",
         "worker_input", "worker_protocol", "worker_exit", "worker_timeout", "container_start",
         "operator_timeout", "engine_failure", "incomplete", "source_changed", "invalid_action", None}
CODES.update({"illegal_action", "initialization_protocol", "joint_action_protocol", "engine_interrupted"})


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def public_feedback(result):
    cases = result.get("cases", [])
    complete = result.get("status") == "scored" and result.get("provenance_verified") is True and len(cases) == result.get("total") and all(c.get("status") == "scored" for c in cases)
    score = result.get("primary_score")
    if not complete or not finite(score) or not 0 <= score <= 1:
        score = None
    metrics = {key: value for key, value in result.get("metrics_mean", {}).items() if key in METRICS and finite(value)} if score is not None else {}
    statuses = collections.Counter(c.get("status") if c.get("status") in STATUSES else "infrastructure_or_incomplete" for c in cases)
    diagnostics = collections.Counter(c.get("diagnostic_code") if c.get("diagnostic_code") in CODES else "other" for c in cases if c.get("status") != "scored")
    error_types = collections.Counter(c.get("error_type") if c.get("error_type") in ERROR_TYPES else "other" for c in cases if c.get("status") != "scored")
    totals = {key: sum(c.get(key, 0) for c in cases if finite(c.get(key))) for key in ("steps", "seconds", "ipc_seconds", "overrides", "action_count", "native_communication_actions")}
    action_count = totals["action_count"]
    return {"status": "scored" if score is not None else "unscored", "total": result.get("total"),
            "scored": statuses["scored"], "primary_score": score, "metrics_mean": metrics,
            "validity_counts": dict(statuses), "diagnostic_counts": dict(diagnostics),
            "error_type_counts": dict(error_types),
            "aggregate_costs": totals, "override_fraction": totals["overrides"] / action_count if action_count else 0.0,
            "provenance_verified": result.get("provenance_verified") is True,
            "infrastructure_affected": result.get("infrastructure_affected") is True,
            "llm_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(public_feedback(json.loads(args.result.read_text())), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

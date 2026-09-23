#!/usr/bin/env python3
"""Original, deliberately small RelayRepair prototype; Python standard library only."""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

PILOT_SEEDS = [1103, 2207, 3301, 4409, 5501, 6607, 7703, 8803, 9901, 10103, 11113, 12109]
CONDITIONS = ("initial", "final_ordered", "final_shuffled", "no_update_shuffled")


def evidence_text(item):
    requirement = (f"must not exceed {item['threshold']}" if item["op"] == "le"
                   else f"must be at least {item['threshold']}")
    return (f"Source {item['id']}, revision {item['revision']}: the reported count is {item['value']}. "
            f"Its requirement is that the count {requirement}. "
            "This source revision replaces all lower revisions of the same source.")


def rule_text(rule):
    groups = ["(" + " AND ".join(group) + ")" for group in rule["supports"]]
    return f"Rule {rule['id']}: it holds exactly when " + " OR ".join(groups) + "."


def valid_source(item):
    if item["op"] == "le":
        return item["value"] <= item["threshold"]
    return item["value"] >= item["threshold"]


def solve_structured(sources, rules, plans):
    state = {key: valid_source(value) for key, value in sources.items()}
    remaining = {rule["id"]: rule for rule in rules}
    while remaining:
        progressed = False
        for key, rule in list(remaining.items()):
            deps = {dep for group in rule["supports"] for dep in group}
            if deps <= state.keys():
                state[key] = any(all(state[dep] for dep in group) for group in rule["supports"])
                del remaining[key]
                progressed = True
        if not progressed:
            raise ValueError("Missing dependency or cyclic rule graph")
    eligible = [p for p in plans if p["requires"] is None or state[p["requires"]]]
    winner = max(eligible, key=lambda p: p["utility"])
    return {"plan_id": winner["id"], "utility": winner["utility"],
            "eligible_plans": [p["id"] for p in eligible], "node_truth": state}


SOURCE_RE = re.compile(r"Source (\w+), revision (\d+): the reported count is (\d+)\. "
                       r"Its requirement is that the count (must not exceed|must be at least) (\d+)\.")
RULE_RE = re.compile(r"Rule (\w+): it holds exactly when (.+)\.")
PLAN_RE = re.compile(r"Plan (\w+) has utility (\d+) and (is always eligible|requires (\w+))\.")


def parse_visible(cards, policy="latest_version"):
    """Reads only strings given to models, never structured oracle data."""
    sources, rule_map, plans = {}, {}, {}
    for card in cards:
        if match := SOURCE_RE.match(card):
            key, revision, value, op, threshold = match.groups()
            item = {"id": key, "revision": int(revision), "value": int(value),
                    "op": "le" if op == "must not exceed" else "ge", "threshold": int(threshold)}
            previous = sources.get(key)
            if previous is None or policy == "latest_arrival" or (
                    policy == "latest_version" and item["revision"] > previous["revision"]):
                sources[key] = item
        elif match := RULE_RE.fullmatch(card):
            key, expr = match.groups()
            rule_map[key] = {"id": key, "supports": [part.strip().strip("()").split(" AND ")
                                                     for part in expr.split(" OR ")]}
        elif match := PLAN_RE.fullmatch(card):
            key, utility, _, requires = match.groups()
            plans[key] = {"id": key, "utility": int(utility), "requires": requires}
        else:
            raise ValueError(f"Unrecognized visible card: {card}")
    return sources, list(rule_map.values()), list(plans.values())


def scripted_answer(cards, policy="latest_version"):
    return solve_structured(*parse_visible(cards, policy))["plan_id"]


INSTRUCTIONS = """Select the highest-utility eligible ML experiment plan from the public plan cards.
You are collaborating with two other agents. Each role has private source and rule cards.
The source owner is authoritative for its source reports. A larger revision number supersedes
every smaller revision of the same source, regardless of arrival order. A retransmitted old
card does not undo a newer revision. Counts are nonnegative integers. A source holds when its
latest count meets the stated numeric requirement. AND requires every named dependency;
OR requires at least one complete support group. Rules can depend on other rules. Public
plan utilities are unique. The fallback is always eligible but is only optimal if every
higher-utility plan is ineligible. The environment guarantees enough evidence across all
three roles to determine one exact best plan. You may exchange evidence and use local code.
Output one JSON object with exactly the key plan_id. Do not invent unobserved revisions.
"""


def generate_case(seed, index):
    rng = random.Random(seed)
    mechanism = ("required_support_lost", "alternate_support_survives", "irrelevant_revision")[index % 3]
    ids = rng.sample(range(1000, 9999), 20)
    source_ids = [f"E{x}" for x in ids[:7]]
    rule_ids = [f"R{x}" for x in ids[7:11]]
    plan_ids = [f"P{x}" for x in ids[11:15]]
    role_ids = [f"agent_{i}" for i in rng.sample([1, 2, 3], 3)]
    owners = {key: role_ids[i % 3] for i, key in enumerate(source_ids)}
    rule_owners = {key: role_ids[(i + 1) % 3] for i, key in enumerate(rule_ids)}
    sources = []
    truth = [True, True, mechanism == "alternate_support_survives", True, True, False, True]
    for key, holds in zip(source_ids, truth):
        threshold = rng.randint(5, 20)
        op = rng.choice(["le", "ge"])
        offset = rng.randint(1, 4)
        value = threshold + (offset if (holds == (op == "ge")) else -offset)
        sources.append({"id": key, "revision": rng.randint(2, 8), "value": value,
                        "op": op, "threshold": threshold, "owner": owners[key]})
    # The top plan uses a support with an optional alternative. The medium plan is stable.
    e, r = source_ids, rule_ids
    rules = [
        {"id": r[0], "supports": [[e[0]], [e[2]]], "owner": rule_owners[r[0]]},
        {"id": r[1], "supports": [[e[1], r[0]]], "owner": rule_owners[r[1]]},
        {"id": r[2], "supports": [[e[3], e[4]], [e[5], e[6]]], "owner": rule_owners[r[2]]},
        {"id": r[3], "supports": [[r[1], e[4]]], "owner": rule_owners[r[3]]},
    ]
    utility = sorted(rng.sample(range(11, 100), 3), reverse=True)
    plans = [{"id": plan_ids[0], "utility": utility[0], "requires": r[3]},
             {"id": plan_ids[1], "utility": utility[1], "requires": r[2]},
             {"id": plan_ids[2], "utility": utility[2], "requires": e[5]},
             {"id": plan_ids[3], "utility": rng.randint(1, 9), "requires": None}]
    rng.shuffle(plans)
    revised_key = e[6] if mechanism == "irrelevant_revision" else e[0]
    old = next(s for s in sources if s["id"] == revised_key)
    update = dict(old)
    update["revision"] += rng.randint(1, 3)
    update["value"] = update["threshold"] + (2 if update["op"] == "le" else -2)
    public = [f"Plan {p['id']} has utility {p['utility']} and " +
              ("is always eligible." if p["requires"] is None else f"requires {p['requires']}.")
              for p in plans]
    initial = [{"owner": item["owner"], "text": evidence_text(item)} for item in sources]
    initial += [{"owner": rule["owner"], "text": rule_text(rule)} for rule in rules]
    rng.shuffle(initial)
    update_card = {"owner": update["owner"], "text": evidence_text(update)}
    ordered = initial + [update_card]
    shuffled = ordered.copy()
    rng.shuffle(shuffled)
    # Explicit delayed retransmission, guaranteed to follow the honest current revision.
    shuffled.append({"owner": old["owner"], "text": evidence_text(old)})
    no_update = initial + [initial[0], initial[-1]]
    rng.shuffle(no_update)
    streams = {"initial": initial, "final_ordered": ordered,
               "final_shuffled": shuffled, "no_update_shuffled": no_update}
    initial_truth = {s["id"]: s for s in sources}
    final_truth = dict(initial_truth)
    final_truth[revised_key] = update
    oracles = {condition: solve_structured(final_truth if condition.startswith("final") else initial_truth,
                                           rules, plans) for condition in CONDITIONS}
    observations = {}
    for condition, stream in streams.items():
        observations[condition] = {
            "instructions": INSTRUCTIONS,
            "public_cards": public,
            "roles": [{"role_id": role, "private_cards": [c["text"] for c in stream if c["owner"] == role]}
                      for role in sorted(role_ids)],
            "central_cards": public + [c["text"] for c in stream],
        }
    return {"case_id": f"relayrepair_{index + 1:02d}", "seed": seed, "mechanism": mechanism,
            "observations": observations,
            "oracle": {"initial_sources": sources, "update": update, "rules": rules, "plans": plans,
                       "answers": oracles, "optimum_changed": oracles["initial"]["plan_id"] !=
                       oracles["final_ordered"]["plan_id"]}}


def evaluate_answer(case, condition, answer):
    if isinstance(answer, dict):
        answer = answer.get("plan_id")
    oracle = case["oracle"]["answers"][condition]
    plan = next((p for p in case["oracle"]["plans"] if p["id"] == answer), None)
    valid = plan is not None and answer in oracle["eligible_plans"]
    utility = plan["utility"] if valid else 0
    return {"exact_success": answer == oracle["plan_id"], "valid_plan": valid,
            "utility": utility, "optimal_utility": oracle["utility"],
            "normalized_utility": utility / oracle["utility"],
            "answer": answer, "expected": oracle["plan_id"]}


def run_controls(cases):
    rows = []
    for case in cases:
        initial = case["observations"]["initial"]["central_cards"]
        for condition in CONDITIONS:
            cards = case["observations"][condition]["central_cards"]
            predictions = {"latest_version_symbolic": scripted_answer(cards),
                           "latest_arrival_stale": scripted_answer(cards, "latest_arrival"),
                           "freeze_initial": scripted_answer(initial), "abstain": None}
            for policy, answer in predictions.items():
                rows.append({"case_id": case["case_id"], "condition": condition, "policy": policy,
                             **evaluate_answer(case, condition, answer)})
    summary = []
    for condition in CONDITIONS:
        for policy in ("latest_version_symbolic", "latest_arrival_stale", "freeze_initial", "abstain"):
            subset = [row for row in rows if row["condition"] == condition and row["policy"] == policy]
            summary.append({"condition": condition, "policy": policy, "n": len(subset),
                            "exact_successes": sum(row["exact_success"] for row in subset),
                            "exact_success_rate": sum(row["exact_success"] for row in subset) / len(subset),
                            "valid_plan_rate": sum(row["valid_plan"] for row in subset) / len(subset),
                            "mean_normalized_utility": sum(row["normalized_utility"] for row in subset) / len(subset)})
    return {"measurement_type": "SCRIPTED_CONTROLS_NOT_MODEL_EVALUATIONS", "summary": summary, "rows": rows}


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    cases = [generate_case(seed, i) for i, seed in enumerate(PILOT_SEEDS)]
    (output / "cases_with_oracle.json").write_text(json.dumps(cases, indent=2) + "\n")
    (output / "model_observations.json").write_text(json.dumps([
        {"case_id": c["case_id"], "observations": c["observations"]} for c in cases], indent=2) + "\n")
    results = run_controls(cases)
    (output / "scripted_results.json").write_text(json.dumps(results, indent=2) + "\n")
    (output / "pilot_manifest.json").write_text(json.dumps({
        "version": "0.1.0", "seeds": PILOT_SEEDS, "cases": 12,
        "conditions": CONDITIONS, "exact_success_denominator_per_condition": 12,
        "optimum_changed_cases": sum(c["oracle"]["optimum_changed"] for c in cases),
        "preregistered_before_model_runs": True,
        "note": "Twelve seeds and case mechanisms fixed before any actual model calls. No model runs included."
    }, indent=2) + "\n")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "generated")
    parser.add_argument("--score", type=Path, help="JSON list of case_id, condition, answer records to score")
    args = parser.parse_args()
    if args.score:
        cases = {case["case_id"]: case for case in json.loads((args.output / "cases_with_oracle.json").read_text())}
        records = json.loads(args.score.read_text())
        print(json.dumps([{**record, "score": evaluate_answer(cases[record["case_id"]], record["condition"], record["answer"])}
                          for record in records], indent=2))
    else:
        print(json.dumps(build(args.output)["summary"], indent=2))


if __name__ == "__main__":
    main()

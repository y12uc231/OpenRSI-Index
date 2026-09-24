"""Separately declared, post-study CPU diagnostic over every submitted controller.

No inference or candidate imports. `run` requires the completed main study and a
new private directory. `export` writes a separate new public directory. Exact
candidate/suite matches may be reused; infrastructure stops without retries.
This does not change the main selection or promote a retrospective best result.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import types

TASK = Path(__file__).resolve().parents[1]
PROTOCOL_SHA = "5aebbcc51e98b2992c587a28ad6cd2b2e7228c658fa6419b55428f406a902115"
DECLARATION_COMMIT = "18a798c39b014229b58456ed716d62a903142b72"
AUDITOR_SHA = "0bb25b94efffdef1ae2997393cb8b44341b42a52bb9bd85a537f061600d97ca5"
DECLARATION = {"declared_at_unix": 1790277646.4344761, "protocol_sha256": PROTOCOL_SHA,
               "main_phase_at_declaration": "model_generation", "calls_attempted": 6,
               "completed_development_candidates": 5, "final_results_available": 0,
               "additional_inference_calls": 0, "maximum_additional_evaluations": 12,
               "declaration_git_commit": DECLARATION_COMMIT}
CALLS = [f"call-{i:02d}" for i in range(1, 7)]
SUITES = ("evaluation", "transfer")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def load_auditor(task):
    path = task / "paper/export_extension.py"
    if path.is_symlink() or sha(path) != AUDITOR_SHA:
        raise ValueError("auditor_identity_mismatch")
    module = types.ModuleType("alem_trajectory_frozen_auditor")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def declaration_record(audit, reader, task, declaration):
    record = reader.obj(declaration)
    audit.require(record == DECLARATION, "diagnostic_declaration_mismatch")
    path = task / "paper/TRAJECTORY-DIAGNOSTIC.md"
    raw = reader.raw(path, PROTOCOL_SHA)
    committed = subprocess.check_output([
        "git", "--no-replace-objects", "show",
        DECLARATION_COMMIT + ":contributor-work/alem-coordination/paper/TRAJECTORY-DIAGNOSTIC.md"],
        cwd=task.parents[1], stderr=subprocess.PIPE, timeout=30)
    audit.require(raw == committed, "diagnostic_protocol_git_mismatch")
    return record


def validate_timing(audit, reader, main_study, summary, declaration):
    declared = declaration["declared_at_unix"]
    frozen = summary.get("selected", {}).get("frozen_at_unix")
    audit.require(audit.finite(frozen) and declared < frozen, "declaration_did_not_precede_selection_freeze")
    starts = []
    for row in summary.get("final", []):
        check = Path(row["check"])
        audit.require(check.is_relative_to(main_study), "main_check_outside_study")
        operator = reader.obj(check / "operator.private.json", root=main_study)
        started = audit.timestamp(operator.get("container_state", {}).get("StartedAt"))
        audit.require(declared < started, "main_final_started_before_diagnostic_declaration")
        starts.append(started)
    audit.require(starts, "main_final_inventory_empty")
    return {"declaration_precedes_selection_freeze": True,
            "declaration_precedes_every_main_final_start": True,
            "main_selection_frozen_at_unix": frozen, "earliest_main_final_start_unix": min(starts),
            "scope": "selection freezes all six candidates; no separate absolute candidate-6 creation timestamp is inferred"}


def tracked_base(audit, reader, task, source, assets):
    spec = reader.obj(task / "baseline/source-manifest.json")
    for name, digest in spec["files"].items():
        reader.raw(source / audit.safe_name(name), digest, root=source)
    spec = reader.obj(task / "baseline/asset-manifest.json")
    for row in spec["files"]:
        audit.require(row["path"].startswith("assets/"), "invalid_asset_prefix")
        reader.raw(assets / audit.safe_name(row["path"][7:]), row["sha256"], root=assets)


def prepare_context(main_study, output, source, assets, declaration, task):
    audit = load_auditor(task)
    reader = audit.Reader()
    summary = reader.obj(main_study / "summary.private.json", root=main_study)
    audit.require(summary.get("status") == "completed" and summary.get("source_unchanged") is True
                  and summary.get("calls_attempted") == 6 and summary.get("declared_calls") == 6,
                  "main_study_not_complete")
    declared = declaration_record(audit, reader, task, declaration)
    timing = validate_timing(audit, reader, main_study, summary, declared)
    # The independent exporter verifies six metadata/response/candidate bindings,
    # source Git blobs, packet, initial parity, every final result and selection.
    main_public = audit.export(main_study, output / "verified-main", task)
    inputs = reader.obj(main_study / "study-inputs.json", root=main_study)
    source_identity, helper = audit.source_identity(reader, inputs, task)
    tracked_base(audit, reader, task, source, assets)
    reader.raw(Path(__file__).resolve())
    reader.raw(task / "paper/export_extension.py", AUDITOR_SHA)
    reader.raw(output / "verified-main/MANIFEST.json")
    candidates = []
    for label in CALLS:
        row = next(r for r in summary["records"] if r["label"] == label)
        original = Path(row["candidate"]) / "controller.py"
        audit.require(original.is_relative_to(main_study), "candidate_outside_main_study")
        raw = reader.raw(original, row["sha256"], root=main_study)
        response = reader.obj(main_study / label / "response.json", root=main_study)
        audit.require(response["controller"].encode("utf-8") == raw, "response_candidate_mismatch")
        reader.raw(main_study / label / "metadata.json", root=main_study)
        snapshot = output / "candidates" / label
        snapshot.mkdir(parents=True)
        (snapshot / "controller.py").write_bytes(raw)
        (snapshot / "controller.py").chmod(0o444)
        reader.raw(snapshot / "controller.py", row["sha256"], root=output)
        candidates.append({"label": label, "sha256": row["sha256"], "bytes": len(raw), "candidate": str(snapshot),
                           "development_status": row["feedback"]["status"],
                           "development_score": row["feedback"].get("primary_score")})
    cache = {}
    for row in main_public["final"]:
        identity = (row["suite"], row["candidate_sha256"])
        if identity in cache:
            continue
        name = row["evaluation"]
        public_path = output / "verified-main/evaluations" / (name + ".json")
        public = reader.obj(public_path, root=output)
        original = next(r for r in summary["final"] if r["label"] == row["label"] and r["suite"] == row["suite"])
        check = Path(original["check"])
        for relative in ("manifest.json", "evaluation.json", "operator.private.json", "output/result.json", "output/feedback.json"):
            reader.raw(check / relative, root=main_study)
        cache[identity] = {"origin": "main", "label": row["label"], "suite": row["suite"],
                           "check": str(check), "public_result": public}
    return {"audit": audit, "reader": reader, "helper": helper, "inputs": inputs, "main_public": main_public,
            "source_identity": source_identity, "timing": timing, "declaration": declared,
            "candidates": candidates, "cache": cache, "main_study": main_study, "task": task}


def unscored_result(audit, candidate, suite, status, diagnostic, executed=False):
    worlds = audit.SUITES[suite]
    return {"suite": suite, "world_ids": worlds, "total": len(worlds), "scored": 0,
            "status": "unscored", "primary_score": None, "metrics_mean": {},
            "candidate_sha256": candidate["sha256"], "execution_attempted": executed,
            "worlds": [{"world_id": world, "status": status, "score": None, "metrics": {}, "costs": {},
                        "diagnostic_code": diagnostic} for world in worlds]}


def run_matrix(context, output, source, assets, evaluation_lock):
    """Exactly twelve report fields, with at most twelve wrapper requests."""
    audit, helper, reader = context["audit"], context["helper"], context["reader"]
    candidates, cache = context["candidates"], dict(context["cache"])
    require = audit.require
    require([c["label"] for c in candidates] == CALLS, "candidate_inventory_mismatch")
    fields = [{"label": c["label"], "suite": suite, "sha256": c["sha256"], "state": "not_run",
               "result": unscored_result(audit, c, suite, "infrastructure_or_incomplete", "diagnostic_not_run")}
              for suite in SUITES for c in candidates]
    status = {"schema_version": 1, "status": "running", "fields": fields, "expected_fields": 12,
              "declaration": context["declaration"], "declaration_timing": context["timing"],
              "main_study": str(context["main_study"]), "main_selected": context["main_public"]["selection"],
              "candidates": candidates, "additional_inference_calls": 0, "automatic_retries": 0,
              "evaluation_requests": 0, "reused_fields": 0, "skipped_invalid_fields": 0,
              "started_at_unix": time.time(), "source_unchanged": False,
              "resources": helper.RESOURCES, "image": helper.DEFAULT_IMAGE}
    start = time.monotonic()
    before = {str(path): value for path, value in reader.reads.items()}
    dump(output / "inputs.private.json", {"files": before, "source_identity": context["source_identity"],
                                          "runner_sha256": sha(Path(__file__)), "auditor_sha256": AUDITOR_SHA})

    def save():
        status["elapsed_seconds"] = time.monotonic() - start
        dump(output / "summary.private.json", status)

    save()
    try:
        for field in fields:
            reader.verify()
            candidate = next(c for c in candidates if c["label"] == field["label"])
            identity = (field["suite"], field["sha256"])
            if identity in cache:
                prior = cache[identity]
                field.update(state="reused", reused_from={k: prior[k] for k in ("origin", "label", "suite")},
                             check=prior.get("check"), result=prior["public_result"])
                status["reused_fields"] += 1
                save()
                continue
            if candidate["bytes"] > helper.MAX_CANDIDATE:
                public = unscored_result(audit, candidate, field["suite"], "candidate_invalid", "candidate_source_exceeds_1_mib")
                field.update(state="candidate_invalid_without_execution", result=public)
                status["skipped_invalid_fields"] += 1
            else:
                check = output / ("check-" + field["label"] + "-" + field["suite"])
                field.update(state="started", check=str(check))
                status["evaluation_requests"] += 1
                require(status["evaluation_requests"] <= 12, "evaluation_budget_exceeded")
                save()
                answer = helper.evaluate(context["task"], source, assets, helper.DEFAULT_IMAGE,
                                         Path(candidate["candidate"]), field["suite"], check,
                                         evaluation_lock, timeout=10800)
                field["operator"] = answer
                if answer.get("operator_status") != "completed" or answer.get("provenance_verified") is not True:
                    field.update(state="infrastructure_or_incomplete", result=unscored_result(
                        audit, candidate, field["suite"], "infrastructure_or_incomplete", "evaluation_infrastructure", True))
                    status["status"] = "unscored_infrastructure"
                    save()
                    break
                public = audit.evaluation(reader, check, field["suite"], candidate["sha256"],
                                          context["task"], context["inputs"], helper)
                field.update(state="evaluated", result=public)
            cache[identity] = {"origin": "diagnostic", "label": field["label"], "suite": field["suite"],
                               "check": field.get("check"), "public_result": public}
            save()
        else:
            status["status"] = "completed"
    except BaseException as exc:
        status["status"] = "unscored_infrastructure"
        status["error_type"] = type(exc).__name__
        for field in fields:
            if field["state"] == "started":
                candidate = next(c for c in candidates if c["label"] == field["label"])
                field.update(state="infrastructure_or_incomplete", result=unscored_result(
                    audit, candidate, field["suite"], "infrastructure_or_incomplete", "evaluation_infrastructure", True))
        save()
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        try:
            reader.verify()
            status["source_unchanged"] = True
        except (OSError, ValueError):
            status["source_unchanged"] = False
            status["status"] = "unscored_source_changed"
        status["finished_at_unix"] = time.time()
        after = {}
        for path in reader.reads:
            try:
                after[str(path)] = sha(path) if path.is_file() and not path.is_symlink() else None
            except OSError:
                after[str(path)] = None
        if after != {str(p): value for p, value in reader.reads.items()}:
            status["source_unchanged"] = False
            status["status"] = "unscored_source_changed"
        dump(output / "verified-files.private.json", {"files": {str(p): value for p, value in reader.reads.items()},
                                                     "after_sha256": after,
                                                     "source_unchanged": status["source_unchanged"]})
        save()
    return status


def run(main_study, output, source, assets, evaluation_lock, declaration, *, task=TASK):
    main_study, output, source, assets, evaluation_lock, declaration, task = map(
        lambda p: Path(p).resolve(), (main_study, output, source, assets, evaluation_lock, declaration, task))
    output.mkdir(parents=True, exist_ok=False)
    try:
        context = prepare_context(main_study, output, source, assets, declaration, task)
    except BaseException as exc:
        dump(output / "failure.private.json", {"status": "preflight_failed", "error_type": type(exc).__name__,
                                               "additional_inference_calls": 0, "evaluation_requests": 0,
                                               "automatic_retries": 0, "time_unix": time.time()})
        raise
    return run_matrix(context, output, source, assets, evaluation_lock)


def validate_matrix_accounting(audit, summary):
    """Reconstruct requests/reuse from the ordered matrix, never summary counters."""
    fields = summary.get("fields", [])
    audit.require([(f.get("suite"), f.get("label")) for f in fields]
                  == [(suite, label) for suite in SUITES for label in CALLS],
                  "diagnostic_matrix_inventory_mismatch")
    audit.require(type(summary.get("expected_fields")) is int and summary["expected_fields"] == 12,
                  "diagnostic_expected_field_count_mismatch")
    counts = {"evaluation_requests": 0, "reused_fields": 0, "skipped_invalid_fields": 0}
    stopped = False
    for field in fields:
        state = field.get("state")
        audit.require(not stopped or state == "not_run", "evaluation_after_infrastructure_stop")
        if state in ("evaluated", "infrastructure_or_incomplete"):
            counts["evaluation_requests"] += 1
        elif state == "reused":
            counts["reused_fields"] += 1
        elif state == "candidate_invalid_without_execution":
            counts["skipped_invalid_fields"] += 1
        elif state != "not_run":
            raise ValueError("unknown_diagnostic_field_state")
        if state in ("infrastructure_or_incomplete", "not_run"):
            audit.require(summary.get("status") == "unscored_infrastructure",
                          "incomplete_field_in_completed_diagnostic")
            # Verification can fail between requests, leaving no explicit failed
            # request. The first not_run still starts a terminal unattempted tail.
            stopped = True
    audit.require(all(type(summary.get(key)) is int and summary[key] == value
                      for key, value in counts.items()), "diagnostic_counter_mismatch")
    return counts


def export(diagnostic, output, *, task=TASK):
    """Public allowlist export; incomplete matrices retain all twelve fields."""
    diagnostic, output, task = Path(diagnostic).resolve(), Path(output).absolute(), Path(task).resolve()
    audit = load_auditor(task)
    require = audit.require
    require(not output.exists(), "output_directory_exists")
    reader = audit.Reader()
    summary = reader.obj(diagnostic / "summary.private.json", root=diagnostic)
    require(summary.get("status") in ("completed", "unscored_infrastructure") and summary.get("source_unchanged") is True,
            "diagnostic_active_or_source_unverified")
    inputs = reader.obj(diagnostic / "inputs.private.json", root=diagnostic)
    final = reader.obj(diagnostic / "verified-files.private.json", root=diagnostic)
    require(inputs.get("runner_sha256") == sha(Path(__file__)) and inputs.get("auditor_sha256") == AUDITOR_SHA,
            "diagnostic_source_identity_mismatch")
    require(final.get("source_unchanged") is True and final.get("after_sha256") == final.get("files")
            and all(final["files"].get(p) == value for p, value in inputs["files"].items()),
            "diagnostic_input_verification_incomplete")
    for path, value in final["files"].items():
        reader.raw(Path(path), value)
    fields = summary.get("fields", [])
    counts = validate_matrix_accounting(audit, summary)
    require(summary.get("additional_inference_calls") == summary.get("automatic_retries") == 0
            and 0 <= summary.get("evaluation_requests", -1) <= 12 and summary.get("declaration") == DECLARATION,
            "diagnostic_declaration_or_budget_mismatch")
    main_manifest = reader.obj(diagnostic / "verified-main/MANIFEST.json", root=diagnostic)
    main = reader.obj(diagnostic / "verified-main/summary.json", main_manifest["files"]["summary.json"], root=diagnostic)
    main_root = Path(summary["main_study"])
    main_input_path = main_root / "study-inputs.json"
    require(str(main_input_path) in inputs["files"], "main_inputs_not_tracked")
    main_inputs = reader.obj(main_input_path, inputs["files"][str(main_input_path)])
    main_summary_path = main_root / "summary.private.json"
    require(str(main_summary_path) in inputs["files"], "main_summary_not_tracked")
    main_summary = reader.obj(main_summary_path, inputs["files"][str(main_summary_path)])
    timing = validate_timing(audit, reader, main_root, main_summary, DECLARATION)
    require(summary.get("declaration_timing") == timing, "diagnostic_timing_record_mismatch")
    require(summary.get("main_selected") == main.get("selection"), "main_selection_record_mismatch")
    _, helper = audit.source_identity(reader, main_inputs, task)
    files, table, comparisons = {}, [], {}
    main_evaluations, cache, observed = {}, {}, {}
    for row in main["final"]:
        key = (row["suite"], row["label"])
        name = "evaluations/" + row["evaluation"] + ".json"
        main_evaluations[key] = reader.obj(diagnostic / "verified-main" / name, main_manifest["files"][name], root=diagnostic)
        cache.setdefault((row["suite"], row["candidate_sha256"]), {"origin": "main", "label": row["label"],
                         "suite": row["suite"], "result": main_evaluations[key]})
    require([c.get("label") for c in summary.get("candidates", [])] == CALLS, "candidate_inventory_mismatch")
    candidates = {c["label"]: c for c in summary["candidates"]}
    stopped = False
    for field in fields:
        candidate = candidates[field["label"]]
        suite, label, identity = field["suite"], field["label"], (field["suite"], field["sha256"])
        main_candidate = next(c for c in main["development"] if c["label"] == label)
        require(candidate["sha256"] == field["sha256"] == main_candidate["sha256"]
                and candidate["development_score"] == main_candidate["primary_score"], "main_candidate_binding_mismatch")
        raw = reader.raw(diagnostic / "candidates" / label / "controller.py", candidate["sha256"], root=diagnostic)
        state = field["state"]
        if stopped:
            require(state == "not_run", "evaluation_after_infrastructure_stop")
        if state == "reused":
            require(identity in cache, "reuse_has_no_prior_identical_result")
            prior = cache[identity]
            require(field.get("reused_from") == {key: prior[key] for key in ("origin", "label", "suite")}, "reuse_reference_mismatch")
            result = prior["result"]
        elif state == "evaluated":
            require(identity not in cache, "identical_result_was_reexecuted")
            check = diagnostic / ("check-" + label + "-" + suite)
            require(field.get("check") == str(check), "diagnostic_check_path_mismatch")
            result = audit.evaluation(reader, check, suite, candidate["sha256"], task, main_inputs, helper)
            cache[identity] = {"origin": "diagnostic", "label": label, "suite": suite, "result": result}
        elif state == "candidate_invalid_without_execution":
            require(len(raw) > helper.MAX_CANDIDATE and identity not in cache, "invalid_source_skip_mismatch")
            result = unscored_result(audit, candidate, suite, "candidate_invalid", "candidate_source_exceeds_1_mib")
            cache[identity] = {"origin": "diagnostic", "label": label, "suite": suite, "result": result}
        elif state in ("infrastructure_or_incomplete", "not_run"):
            require(summary["status"] == "unscored_infrastructure", "incomplete_field_in_completed_diagnostic")
            if state == "infrastructure_or_incomplete":
                stopped = True
            result = unscored_result(audit, candidate, suite, "infrastructure_or_incomplete",
                                     "evaluation_infrastructure" if state == "infrastructure_or_incomplete" else "diagnostic_not_run",
                                     state == "infrastructure_or_incomplete")
        else:
            raise ValueError("unknown_diagnostic_field_state")
        require(result == field["result"], "stored_result_differs_from_verified_evidence")
        observed[(suite, label)] = result
    for candidate in summary["candidates"]:
        label = candidate["label"]
        require(label in CALLS, "unknown_candidate_label")
        raw = reader.raw(diagnostic / "candidates" / label / "controller.py", candidate["sha256"], root=diagnostic)
        require(not audit.PRIVATE.search(raw.decode("utf-8")), "sensitive_candidate_requires_review")
        files["candidates/" + label + "/controller.py"] = raw
        line = {"label": label, "sha256": candidate["sha256"], "development_status": candidate["development_status"],
                "development_score": candidate["development_score"], "suites": {}}
        comparisons[label] = {}
        for suite in SUITES:
            field = next(f for f in fields if f["suite"] == suite and f["label"] == label)
            require(field["sha256"] == candidate["sha256"], "matrix_candidate_mismatch")
            result = observed[(suite, label)]
            require(result.get("world_ids") == audit.SUITES[suite] and [w.get("world_id") for w in result.get("worlds", [])] == audit.SUITES[suite],
                    "diagnostic_world_inventory_mismatch")
            name = "evaluations/" + suite + "-" + label + ".json"
            files[name] = audit.encoded(result)
            line["suites"][suite] = {"state": field["state"], "status": result["status"], "primary_score": result["primary_score"],
                                     "evaluation": name, "reused_from": field.get("reused_from"),
                                     "operator_costs": {key: field["operator"][key] for key in ("seconds", "queue_seconds", "returncode")
                                                        if audit.finite(field.get("operator", {}).get(key))}}
            comparisons[label][suite] = {"minus_reference": audit.paired(result, main_evaluations[(suite, "reference")]),
                                          "minus_incumbent": audit.paired(result, main_evaluations[(suite, "incumbent")])}
        table.append(line)
    public = {"schema_version": 1, "status": summary["status"], "scope": "separately declared trajectory diagnostic",
              "declaration": DECLARATION, "declaration_timing": timing,
              "main_selection_unchanged": main["selection"], "candidates": table,
              "additional_inference_calls": 0, "automatic_retries": 0,
              "evaluation_requests": counts["evaluation_requests"], "reused_fields": counts["reused_fields"],
              "skipped_invalid_fields": counts["skipped_invalid_fields"], "elapsed_seconds": summary["elapsed_seconds"],
              "resources": summary["resources"], "image": summary["image"],
              "runner_sha256": inputs["runner_sha256"], "auditor_sha256": AUDITOR_SHA,
              "source_identity": inputs["source_identity"], "source_unchanged": True,
              "limitations": ["Declared after five development results, before final results; separate from the primary experiment",
                              "Six adaptive submissions are not independent researcher attempts",
                              "Any better rejected controller is a retrospective fixed-set observation, not a new selected winner",
                              "Regression worlds and transfer worlds are distinct fixed sets from the same generator",
                              "All twelve fields are retained; incomplete fields do not acquire a mean",
                              "Descriptive paired differences only; no confidence intervals"]}
    files["summary.json"] = audit.encoded(public)
    files["comparison.json"] = audit.encoded(comparisons)
    reader.verify()
    for name, raw in files.items():
        audit.safe_name(name)
        require(not audit.PRIVATE.search(raw.decode("utf-8")), "private_data_in_public_export")
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    dump(output / "MANIFEST.json", {"files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())},
                                    "runner_sha256": inputs["runner_sha256"], "protocol_sha256": PROTOCOL_SHA,
                                    "private_prompts_notes_reasoning_or_logs_included": False})
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    execute = sub.add_parser("run")
    for name in ("main-study", "output", "source", "assets", "evaluation-lock", "declaration"):
        execute.add_argument("--" + name, type=Path, required=True)
    publish = sub.add_parser("export")
    publish.add_argument("--diagnostic", type=Path, required=True)
    publish.add_argument("--output", type=Path, required=True)
    args = vars(parser.parse_args())
    mode = args.pop("mode")
    result = run(**args) if mode == "run" else export(**args)
    print(json.dumps({"status": result["status"], "additional_inference_calls": 0,
                      "evaluation_requests": result["evaluation_requests"]}))
    if result["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

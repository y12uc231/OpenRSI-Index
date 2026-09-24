"""Export a completed six-call continuation; never import generated candidates.

Only allowlisted evidence is public. Prompts, response notes, reasoning/events,
operator commands, arbitrary exception strings and private paths are excluded.
Actor stderr is read only to count declared suppression markers; it is not copied.
This produces descriptive paired differences, not confidence intervals or claims
of independent researcher samples. A new output directory is required.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import subprocess
import types

TASK = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "9c8b6320b48463de9cde0d9a8b55911f99a689bd"
TASK_REPO_PATH = "contributor-work/alem-coordination"
TRANSPORT_REPO_PATH = "contributor-work/relayrepair/pilot/codex_runner.py"
PACKET_SHA = "d64f2fe9425d12ae34f3e00c1ca0743e7a60569102b687195bc6c9b6a912bea3"
SOL_SHA = "3862d57dbf57dbb8e1f2efff6cd32a345dd7006a0dab58d40b45e0ff5ae38d89"
PARITY_SHAS = {"reference": "f63346bf8e87b6bcc1d2330658eed55427b5fcd1a12f54f2b46b9763ff9560f2",
               "incumbent": "1db38ea3608ba8cac70d034b469e8caeaa99fa5ddad4ded2683430f50b8f1e6a"}
PRIMARY = "Team/coord_reward_pct_of_max"
SUITES = {"dev": list(range(20000, 20004)), "evaluation": list(range(9999, 10019)), "transfer": list(range(30000, 30020))}
CALLS = [f"call-{i:02d}" for i in range(1, 7)]
DEVELOPMENT = ["reference", "incumbent"] + CALLS
MODES = ("reset_explicit_json_memory", "suppress_controller_added_comm")
TOKENS = ("input_tokens", "output_tokens", "cached_input_tokens", "cache_write_input_tokens", "reasoning_output_tokens", "total_tokens")
COSTS = ("steps", "seconds", "ipc_seconds", "overrides", "action_count", "policy_forward_batches", "controller_calls", "native_communication_actions")
STATUSES = ("scored", "candidate_invalid", "infrastructure_or_incomplete")
HEX = re.compile(r"[0-9a-f]{64}\Z")
PRIVATE = re.compile(r"/Users/|/home/|/var/folders/|/private/var/|[A-Za-z]:\\Users\\|(?:sk-proj-|sk-|gh[pousr]_|github_pat_)[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}")
MARKER = b"ALEM_PAPER_ADDED_COMM_SUPPRESSED_V1"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def close(a, b):
    return finite(a) and finite(b) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def require(condition, category):
    if not condition:
        raise ValueError(category)


def safe_code(value):
    if value is None:
        return None
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", value) else "other"


def safe_hash(value):
    require(isinstance(value, str) and HEX.fullmatch(value), "invalid_digest")
    return value


def safe_name(value):
    require(isinstance(value, str) and "\\" not in value and not PRIVATE.search(value), "unsafe_artifact_name")
    path = PurePosixPath(value)
    require(not path.is_absolute() and value == path.as_posix() and all(p not in (".", "..") for p in path.parts), "unsafe_artifact_name")
    return value


class Reader:
    def __init__(self):
        self.reads = {}

    def raw(self, path, expected=None, root=None):
        path = Path(path)
        require(path.is_absolute(), "input_path_not_absolute")
        require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), "nonregular_input")
        if root is not None:
            require(path.is_relative_to(root), "input_outside_declared_root")
        raw = path.read_bytes()
        digest = sha(raw)
        require(expected is None or digest == expected, "input_hash_mismatch")
        require(path not in self.reads or self.reads[path] == digest, "input_changed_during_export")
        self.reads[path] = digest
        return raw

    def obj(self, path, expected=None, root=None):
        def invalid(value):
            raise ValueError("nonfinite_json")
        return json.loads(self.raw(path, expected, root), parse_constant=invalid)

    def verify(self):
        for path, digest in list(self.reads.items()):
            self.raw(path, digest)


def token_metadata(value):
    require(isinstance(value, dict) and value.get("status") == "completed" and value.get("return_code") == 0
            and value.get("tool_free") is True and value.get("model_requested") == "gpt-6-sol"
            and value.get("reasoning_effort") == "ultra", "incomplete_call_metadata")
    records = value.get("usage")
    require(isinstance(records, list) and len(records) == 1 and isinstance(records[0], dict), "invalid_usage_inventory")
    record = records[0]
    require(set(record) <= set(TOKENS), "unknown_usage_field_requires_review")
    require(all(type(record.get(k)) is int and record[k] >= 0 for k in ("input_tokens", "output_tokens")), "missing_token_counts")
    usage = {}
    for key in TOKENS:
        if key in record:
            require(type(record[key]) is int and record[key] >= 0, "invalid_token_count")
            usage[key] = record[key]
    for subset, parent in (("cached_input_tokens", "input_tokens"), ("cache_write_input_tokens", "input_tokens"), ("reasoning_output_tokens", "output_tokens")):
        require(subset not in usage or usage[subset] <= usage[parent], "token_subset_exceeds_parent")
    require("total_tokens" not in usage or usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"], "inconsistent_total_tokens")
    require(finite(value.get("seconds")) and value["seconds"] >= 0, "invalid_call_time")
    return {"status": "completed", "model_requested": "gpt-6-sol", "reasoning_effort": "ultra",
            "model_identity": "requested alias; no immutable server snapshot exposed", "tool_free": True,
            "seconds": value["seconds"], "usage": usage,
            "input_plus_output_tokens": usage["input_tokens"] + usage["output_tokens"]}


def scalar_metrics(value):
    require(isinstance(value, dict), "invalid_metrics")
    result = {}
    for key, number in value.items():
        # Metric values are numeric only; no user-generated nested data or strings.
        require(isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)+", key)
                and finite(number), "invalid_native_metric")
        result[key] = number
    return result


def initial_parity(reader, inputs, row, check):
    paths = [Path(path) for path, digest in inputs["files"].items() if digest == PARITY_SHAS[row["label"]]]
    require(len(paths) == 1, "initial_parity_input_missing_or_ambiguous")
    old = reader.obj(paths[0], PARITY_SHAS[row["label"]])
    new = reader.obj(check / "output/result.json", root=check)
    fields = ("world_id", "status", "steps", "naturally_terminated", "score", "metrics",
              "overrides", "action_count", "native_communication_actions", "trace_sha256")
    require(old.get("world_ids") == new.get("world_ids") == SUITES["dev"]
            and len(old.get("cases", [])) == len(new.get("cases", [])) == 4
            and all(all(a.get(k) == b.get(k) for k in fields) for a, b in zip(old["cases"], new["cases"])),
            "initial_development_game_history_mismatch")


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", value), "invalid_container_start_time")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def read_committed_blob(repo, name):
    """Read immutable Git objects only, ignoring replace-object redirection."""
    safe_name(name)
    require(name.startswith(TASK_REPO_PATH + "/") or name == TRANSPORT_REPO_PATH, "unapproved_repository_input")
    return subprocess.check_output(["git", "--no-replace-objects", "show", SOURCE_COMMIT + ":" + name],
                                   cwd=repo, stderr=subprocess.PIPE, timeout=30)


def external_inputs(reader, inputs):
    files = inputs["files"]
    manifests = [Path(path) for path, digest in files.items() if digest == PACKET_SHA and Path(path).name == "MANIFEST.json"]
    require(len(manifests) == 1, "fixed_packet_manifest_missing_or_ambiguous")
    manifest_path = manifests[0]
    manifest = reader.obj(manifest_path, PACKET_SHA)
    require(isinstance(manifest, dict) and manifest == inputs.get("packet_manifest"), "packet_manifest_identity_mismatch")
    expected = {manifest_path: PACKET_SHA}
    for name, digest in manifest.items():
        path = manifest_path.parent / safe_name(name)
        require(files.get(str(path)) == safe_hash(digest), "packet_file_inventory_mismatch")
        reader.raw(path, digest, root=manifest_path.parent)
        expected[path] = digest
    for digest in PARITY_SHAS.values():
        matches = [Path(path) for path, value in files.items() if value == digest]
        require(len(matches) == 1, "initial_parity_input_missing_or_ambiguous")
        reader.raw(matches[0], digest)
        expected[matches[0]] = digest
    return expected


def source_identity(reader, inputs, task):
    files = inputs.get("files")
    require(isinstance(files, dict) and files, "missing_source_inventory")
    external = external_inputs(reader, inputs)
    repo = task.parents[1]
    transport = task.parent / "relayrepair/pilot/codex_runner.py"
    require(str(transport) in files, "transport_source_missing")
    normalized, outside, anchored = {}, 0, {}
    for value, digest in sorted(files.items()):
        path = Path(value)
        raw = reader.raw(path, safe_hash(digest))
        require(path == path.resolve(), "noncanonical_source_path")
        if path.is_relative_to(task):
            relative = path.relative_to(task).as_posix()
            committed = read_committed_blob(repo, TASK_REPO_PATH + "/" + relative)
            require(raw == committed, "repository_input_differs_from_frozen_commit")
            anchored[path] = committed
            name = "task/" + relative
        elif path == transport:
            committed = read_committed_blob(repo, TRANSPORT_REPO_PATH)
            require(raw == committed, "repository_input_differs_from_frozen_commit")
            anchored[path] = committed
            name = "transport/codex_runner.py"
        else:
            require(external.get(path) == digest, "unanchored_external_input")
            # Full private filenames are unnecessary for immutable input identity.
            outside += 1
            name = f"external-input-{outside:03d}"
        normalized[safe_name(name)] = digest
    mandatory = ("paper/run_evaluation.py", "paper/run_extension.py", "paper/make_ablations.py",
                 "paper/EXTENSION-PROTOCOL.md", "controller/feedback.py",
                 "baseline/source-manifest.json", "baseline/asset-manifest.json")
    require(all(str(task / name) in files for name in mandatory), "incomplete_source_inventory")
    require(inputs.get("protocol_sha256") == files[str(task / "paper/EXTENSION-PROTOCOL.md")], "protocol_identity_mismatch")
    # Only trusted source that was frozen before inference is loaded. Candidates
    # are byte artifacts throughout this exporter and are never imported/compiled.
    helper = types.ModuleType("alem_extension_verified_evaluator")
    path = task / "paper/run_evaluation.py"
    helper.__file__ = str(path)
    exec(compile(anchored[path], str(path), "exec"), helper.__dict__)
    return normalized, helper


def suppression_count(reader, check, raw):
    """Unknown if logs are missing/truncated; never infer zero from absence."""
    unknown = {"status": "unknown", "count": None,
               "limitation": "diagnostic markers are not secure against deliberately forged candidate output"}
    try:
        launch = reader.obj(check / "output/launch.private.json", root=check)
        traffic = launch["process_traffic"]
        worlds = raw["world_ids"]
        require(raw["status"] == "scored" and len(traffic) == len(worlds) * 3 + 1
                and launch.get("source_candidate_unchanged") is True and not launch.get("cleanup_incomplete"), "incomplete_actor_logs")
        actors = traffic[:-1]
        require(all(isinstance(row, dict) and row.get("stderr_truncated") is False
                    and type(row.get("stderr_bytes")) is int and row["stderr_bytes"] >= 0 for row in actors), "truncated_actor_logs")
        expected = [f"world-{world}-actor-{actor}.stderr.txt" for world in worlds for actor in range(3)]
        present = {p.name for p in (check / "output").glob("world-*-actor-*.stderr.txt")}
        require(present == set(expected), "actor_log_inventory_mismatch")
        count = 0
        for name, record in zip(expected, actors):
            data = reader.raw(check / "output" / name, root=check)
            require(len(data) == record["stderr_bytes"], "actor_log_byte_count_mismatch")
            count += sum(line == MARKER for line in data.splitlines())
        return {**unknown, "status": "complete", "count": count,
                "actor_log_files": len(expected), "all_actor_stderr_untruncated": True}
    except (KeyError, TypeError, OSError, ValueError):
        return unknown


def evaluation(reader, check, suite, candidate_hash, task, inputs, helper, suppression=False):
    check = Path(check)
    manifest = reader.obj(check / "manifest.json", root=check)
    audit = reader.obj(check / "evaluation.json", root=check)
    require(audit.get("operator_status") == "completed" and audit.get("provenance_verified") is True
            and audit.get("candidate_sha256") == candidate_hash and audit.get("suite") == suite
            and audit.get("manifest_sha256") == reader.reads[check / "manifest.json"], "evaluation_audit_mismatch")
    require(manifest.get("suite") == suite and manifest.get("world_ids") == SUITES[suite]
            and manifest.get("candidate_sha256") == candidate_hash, "evaluation_manifest_mismatch")
    require(manifest.get("wrapper_sha256") == inputs["files"][str(task / "paper/run_evaluation.py")], "wrapper_identity_mismatch")
    require(manifest.get("resources") == helper.RESOURCES and manifest.get("env") == helper.ENV
            and manifest.get("image") == helper.DEFAULT_IMAGE and manifest.get("automatic_retries") == 0, "resource_or_image_mismatch")
    files = manifest["files"]
    require(isinstance(files, dict) and files and set(files) == set(manifest["original_files"]), "staged_inventory_mismatch")
    actual_names = set()
    for path in (check / "stage").rglob("*"):
        require(not path.is_symlink() and (path.is_dir() or path.is_file()), "nonregular_staging")
        if path.is_file():
            actual_names.add(path.relative_to(check / "stage").as_posix())
    require(actual_names == set(files), "staged_inventory_mismatch")
    for name, digest in files.items():
        safe_name(name)
        reader.raw(check / "stage" / name, safe_hash(digest), root=check)
    originals = manifest["original_files"]
    for name in helper.NATIVE:
        path = task / "native" / name
        require(originals.get("task/native/" + name) == inputs["files"].get(str(path)), "original_native_identity_mismatch")
    for name in helper.CONTROLLER:
        path = task / "controller" / name
        require(originals.get("task/controller/" + name) == inputs["files"].get(str(path)), "original_controller_identity_mismatch")
    changes = {name for name in files if files[name] != originals[name]}
    wanted = {"task/native/run.py", "task/native/engine.py"} if suite == "transfer" else set()
    require(changes == wanted, "unexpected_scientific_patch")
    if suite == "transfer":
        replacements = {
            "run.py": [("FrameProcess, SUITES = launcher.FrameProcess, launcher.SUITES", "FrameProcess, SUITES = launcher.FrameProcess, {**launcher.SUITES, 'transfer': list(range(30000, 30020))}")],
            "engine.py": [("choices=('dev','evaluation')", "choices=('dev','evaluation','transfer')"),
                          ("worlds=list(range(20000,20004)) if args.suite=='dev' else list(range(9999,10019))", "worlds={'dev':list(range(20000,20004)), 'evaluation':list(range(9999,10019)), 'transfer':list(range(30000,30020))}[args.suite]")]}
        for name, pairs in replacements.items():
            text = reader.raw(task / "native" / name).decode()
            for before, after in pairs:
                require(text.count(before) == 1, "transfer_patch_source_drift")
                text = text.replace(before, after)
            require(sha(text.encode()) == files["task/native/" + name], "transfer_patch_mismatch")
    reader.raw(check / "transfer.patch", manifest["transfer_patch_sha256"], root=check)
    source = reader.obj(task / "baseline/source-manifest.json")
    assets = reader.obj(task / "baseline/asset-manifest.json")
    expected_source = {"app/" + name: value for name, value in source["files"].items()}
    expected_assets = {row["path"]: row["sha256"] for row in assets["files"]}
    require(manifest.get("source_revision") == source["revision"] and manifest.get("asset_revision") == assets["revision"], "upstream_revision_mismatch")
    require({k: v for k, v in files.items() if k.startswith("app/")} == expected_source
            and {k: v for k, v in files.items() if k.startswith("assets/")} == expected_assets, "source_or_checkpoint_inventory_mismatch")
    task_names = (["native/" + name for name in helper.NATIVE] + ["controller/" + name for name in helper.CONTROLLER]
                  + ["baseline/source-manifest.json", "baseline/asset-manifest.json", "TASK_DESIGN.md"])
    expected_originals = {**expected_source, **expected_assets, "candidate/controller.py": candidate_hash,
                          **{"task/" + name: inputs["files"].get(str(task / name)) for name in task_names}}
    require(originals == expected_originals, "minimal_staging_identity_mismatch")
    raw = reader.obj(check / "output/result.json", audit["result_sha256"], root=check)
    reader.obj(check / "output/feedback.json", audit["feedback_sha256"], root=check)
    problems, mean = helper.validate_result(raw, manifest)
    require(not problems and audit.get("primary_score") == mean, "native_result_validation_failed")
    operator = reader.obj(check / "operator.private.json", root=check)
    state = operator.get("container_state") or {}
    require(operator.get("returncode") == 0 and operator.get("error_type") is None and operator.get("cleanup_ok") is True
            and operator.get("resources") == helper.RESOURCES and operator.get("image", {}).get("Id") == manifest["image"]
            and state.get("Running") is False and state.get("OOMKilled") is False and state.get("ExitCode") == 0,
            "operator_exit_mismatch")
    rows = []
    for case in raw["cases"]:
        rows.append({"world_id": case["world_id"], "status": case["status"], "score": case.get("score"),
                     "naturally_terminated": case.get("naturally_terminated") is True,
                     "metrics": scalar_metrics(case.get("metrics", {})),
                     "costs": {key: case[key] for key in COSTS if finite(case.get(key))},
                     "trace_sha256": safe_hash(case["trace_sha256"]) if case.get("trace_sha256") is not None else None,
                     "diagnostic_code": safe_code(case.get("diagnostic_code")), "error_type": safe_code(case.get("error_type"))})
    metrics = scalar_metrics(raw.get("metrics_mean") or {})
    require(mean is not None or not metrics, "incomplete_suite_has_aggregate_metrics")
    if mean is not None:
        require(all(set(row["metrics"]) == set(metrics) for row in rows), "metric_inventory_mismatch")
        for key, value in metrics.items():
            require(close(value, sum(row["metrics"][key] for row in rows) / len(rows)), "metric_mean_mismatch")
    label = {"dev": "development", "evaluation": "original_public_regression", "transfer": "fresh_same_generator_transfer"}[suite]
    public = {"suite": suite, "interpretation": label, "world_ids": SUITES[suite], "total": len(rows),
              "status": raw["status"], "scored": raw["scored"], "primary_score": mean, "metrics_mean": metrics,
              "worlds": rows, "candidate_sha256": candidate_hash, "provenance_verified": True,
              "image": manifest["image"], "resources": helper.RESOURCES,
              "source_revision": manifest["source_revision"], "asset_revision": manifest["asset_revision"],
              "source_file_sha256": expected_source, "asset_file_sha256": expected_assets,
              "native_sha256": helper.expected_hashes(manifest)["native_sha256"],
              "runner_sha256": helper.expected_hashes(manifest)["runner_sha256"],
              "manifest_sha256": reader.reads[check / "manifest.json"], "raw_result_sha256": reader.reads[check / "output/result.json"],
              "transfer_patch_sha256": manifest["transfer_patch_sha256"],
              "operator": {key: operator[key] for key in ("returncode", "seconds", "queue_seconds") if finite(operator.get(key))},
              "automatic_retries": 0, "llm_calls": 0}
    if suppression:
        public["suppression_diagnostic"] = suppression_count(reader, check, raw)
    public["operator"]["started_at_unix"] = timestamp(state.get("StartedAt"))
    return public


def paired(a, b):
    require(a["world_ids"] == b["world_ids"], "paired_world_mismatch")
    rows = []
    for left, right in zip(a["worlds"], b["worlds"]):
        delta = left["score"] - right["score"] if left["status"] == right["status"] == "scored" else None
        rows.append({"world_id": left["world_id"], "left_status": left["status"], "right_status": right["status"],
                     "left_score": left["score"], "right_score": right["score"], "difference": delta})
    full = all(row["difference"] is not None for row in rows)
    differences = [row["difference"] for row in rows] if full else []
    return {"worlds": rows, "total": len(rows), "valid_pairs": sum(row["difference"] is not None for row in rows),
            "mean_difference": statistics.mean(differences) if full else None,
            "median_difference": statistics.median(differences) if full else None,
            "min_difference": min(differences) if full else None, "max_difference": max(differences) if full else None,
            "sample_sd_difference": statistics.stdev(differences) if full and len(rows) > 1 else None,
            "better": sum(d > 0 for d in differences) if full else None,
            "equal": sum(d == 0 for d in differences) if full else None,
            "worse": sum(d < 0 for d in differences) if full else None,
            "largest_absolute_contributions": [{"world_id": row["world_id"], "difference": row["difference"],
                                                 "contribution_to_mean": row["difference"] / len(rows)}
                                                for row in sorted(rows, key=lambda row: -abs(row["difference"]))[:5]] if full else [],
            "inference": "descriptive paired comparison only; no confidence interval or population claim"}


def export(study, output, task=TASK):
    study, output, task = Path(study).resolve(), Path(output).absolute(), Path(task).resolve()
    require(not output.exists(), "output_directory_exists")
    reader = Reader()
    summary = reader.obj(study / "summary.private.json", root=study)
    inputs = reader.obj(study / "study-inputs.json", root=study)
    require(summary.get("status") == "completed" and summary.get("phase") == "complete"
            and summary.get("source_unchanged") is True and summary.get("calls_attempted") == 6
            and summary.get("declared_calls") == inputs.get("declared_calls") == 6, "study_not_complete_six_calls")
    require(inputs.get("model_requested") == summary.get("model_requested") == "gpt-6-sol"
            and inputs.get("reasoning_effort") == "ultra" and inputs.get("fresh_worlds") == SUITES["transfer"]
            and inputs.get("original_worlds") == SUITES["evaluation"], "study_declaration_mismatch")
    require(inputs.get("source_commit") == SOURCE_COMMIT and inputs.get("starting_sol_sha256") == SOL_SHA, "frozen_study_identity_mismatch")
    source_map, helper = source_identity(reader, inputs, task)
    for prefix, expected in (("call-", set(CALLS)), ("candidate-", {f"candidate-{i:02d}" for i in range(1, 7)})):
        entries = {p.name for p in study.iterdir() if p.name.startswith(prefix)}
        require(entries == expected, "generation_directory_inventory_mismatch")
    records = summary.get("records")
    require(isinstance(records, list) and [r.get("label") for r in records] == DEVELOPMENT, "development_record_inventory_mismatch")
    files, calls, totals, dev, evaluations = {}, [], Counter(), [], {}
    exported_candidate = {}

    def candidate(label, path, expected):
        path = Path(path) / "controller.py"
        require(path.is_relative_to(study) or path.is_relative_to(task), "candidate_outside_allowed_roots")
        raw = reader.raw(path, safe_hash(expected))
        require(not PRIVATE.search(raw.decode("utf-8")), "sensitive_pattern_in_candidate_requires_review")
        name = f"candidates/{label}/controller.py"
        files[name] = raw
        exported_candidate[label] = expected
        return name

    def check(row, suite, key, suppression=False):
        path = Path(row["check"])
        require(path.is_relative_to(study), "evaluation_outside_study")
        public = evaluation(reader, path, suite, row["sha256"], task, inputs, helper, suppression)
        require(row["feedback"].get("status") == public["status"]
                and row["feedback"].get("primary_score") == public["primary_score"], "record_feedback_mismatch")
        evaluations[key] = public
        files[f"evaluations/{key}.json"] = encoded(public)
        return public

    for index, row in enumerate(records):
        label = row["label"]
        name = candidate(label, row["candidate"], row["sha256"])
        key = "dev-" + label
        if index < 2:
            require(row.get("deployment_parity") is True, "initial_deployment_parity_not_verified")
            if label == "incumbent":
                require(row["sha256"] == SOL_SHA, "original_sol_identity_mismatch")
        if index >= 2:
            call = token_metadata(reader.obj(study / label / "metadata.json", root=study))
            call["label"], call["candidate_sha256"] = label, row["sha256"]
            calls.append(call)
            totals.update(call["usage"])
            response = reader.obj(study / label / "response.json", root=study)
            require(isinstance(response, dict) and set(response) == {"controller", "note"}
                    and isinstance(response["controller"], str) and isinstance(response["note"], str)
                    and response["controller"].encode("utf-8") == files[name], "model_response_candidate_bytes_mismatch")
        invalid_path = Path(row["check"]) / "candidate-invalid.json"
        if invalid_path.exists():
            invalid = reader.obj(invalid_path, root=study)
            require(index >= 2 and len(files[name]) > 1024 * 1024 and invalid.get("status") == "unscored"
                    and invalid.get("execution_attempted") is False and invalid.get("primary_score") is None
                    and invalid.get("diagnostic_counts") == {"candidate_source_exceeds_1_mib": 1}, "invalid_skipped_candidate_record")
            public = {"suite": "dev", "status": "unscored", "primary_score": None, "total": 4, "scored": 0,
                      "world_ids": SUITES["dev"], "candidate_sha256": row["sha256"], "execution_attempted": False,
                      "worlds": [{"world_id": world, "status": "candidate_invalid", "score": None, "metrics": {},
                                  "diagnostic_code": "candidate_source_exceeds_1_mib"} for world in SUITES["dev"]]}
            evaluations[key] = public
            files[f"evaluations/{key}.json"] = encoded(public)
        else:
            public = check(row, "dev", key)
        if index < 2:
            initial_parity(reader, inputs, row, Path(row["check"]))
        dev.append({"label": label, "candidate_file": name, "sha256": row["sha256"], "evaluation": key,
                    "status": public["status"], "primary_score": public["primary_score"]})
    recorded_usage = summary.get("usage", {})
    require(recorded_usage.get("usage_complete") is True
            and [r.get("call") for r in recorded_usage.get("calls", [])] == CALLS
            and {k: v for k, v in recorded_usage.get("known_usage", {}).items() if k in TOKENS} == dict(totals)
            and recorded_usage.get("input_plus_output_tokens") == totals["input_tokens"] + totals["output_tokens"], "usage_summary_mismatch")
    eligible = [r for r in dev if r["status"] == "scored"]
    require(eligible, "no_valid_development_candidate")
    winner = max(eligible, key=lambda row: row["primary_score"])
    selected = reader.obj(study / "selection.json", root=study)
    require(selected == summary.get("selected") and selected.get("label") == winner["label"]
            and selected.get("sha256") == winner["sha256"]
            and selected.get("feedback", {}).get("primary_score") == winner["primary_score"], "selection_rule_mismatch")
    require(finite(selected.get("frozen_at_unix")) and selected["frozen_at_unix"] > 0, "selection_time_missing")
    candidate("selected", study / "selected", selected["sha256"])
    labels = ["reference", "incumbent", "selected"]
    unavailable = summary.get("unavailable_ablations", [])
    require(isinstance(unavailable, list) and len({r.get("intervention") for r in unavailable}) == len(unavailable)
            and all(r.get("intervention") in MODES and r.get("status") == "unscored" for r in unavailable), "invalid_unavailable_ablation_inventory")
    if selected["sha256"] == dev[0]["sha256"]:
        require(summary.get("ablation_status") == "not_run_selected_pass_through" and not unavailable, "pass_through_ablation_mismatch")
    else:
        wrapper = types.ModuleType("alem_extension_verified_ablation_builder")
        wrapper_path = task / "paper/make_ablations.py"
        wrapper.__file__ = str(wrapper_path)
        committed = read_committed_blob(task.parents[1], TASK_REPO_PATH + "/paper/make_ablations.py")
        require(reader.raw(wrapper_path) == committed, "repository_input_differs_from_frozen_commit")
        exec(compile(committed, str(wrapper_path), "exec"), wrapper.__dict__)
        for mode in MODES:
            omitted = next((row for row in unavailable if row["intervention"] == mode), None)
            try:
                expected = wrapper.wrapped(files["candidates/selected/controller.py"].decode("utf-8"), mode).encode("utf-8")
            except (ValueError, SyntaxError, UnicodeError) as exc:
                require(omitted is not None and omitted.get("error_type") == type(exc).__name__, "ablation_rejection_mismatch")
                continue
            require(omitted is None, "available_ablation_cannot_be_omitted")
            path = study / ("ablation-" + mode)
            record = reader.obj(path / "intervention.json", root=study)
            require(record.get("intervention") == mode and record.get("original_sha256") == selected["sha256"]
                    and record.get("wrapper_source_sha256") == inputs["files"][str(task / "paper/make_ablations.py")], "ablation_provenance_mismatch")
            name = candidate(mode, path, record["wrapped_sha256"])
            require(files[name] == expected, "ablation_bytes_differ_from_declared_intervention")
            labels.append(mode)
    final = summary.get("final")
    require(isinstance(final, list) and [(r.get("suite"), r.get("label")) for r in final] == [(s, label) for s in ("evaluation", "transfer") for label in labels], "final_record_inventory_mismatch")
    final_public, seen, arm_keys = [], {}, {}
    for row in final:
        label, suite = row["label"], row["suite"]
        require(row["sha256"] == exported_candidate[label], "final_candidate_identity_mismatch")
        identity = (suite, row["sha256"])
        if identity in seen:
            prior = seen[identity]
            require(row.get("reused_from") == prior["label"] and row["check"] == prior["check"]
                    and row["feedback"] == prior["feedback"], "evaluation_reuse_mismatch")
            key = arm_keys[(suite, prior["label"])]
            reused_from = prior["label"]
        else:
            require("reused_from" not in row, "unverified_evaluation_reuse")
            key = suite + "-" + label
            check(row, suite, key, suppression=label == MODES[1])
            require(evaluations[key]["operator"]["started_at_unix"] >= selected["frozen_at_unix"], "final_evaluation_precedes_selection")
            seen[identity] = row
            reused_from = None
        arm_keys[(suite, label)] = key
        final_public.append({"label": label, "suite": suite, "candidate_sha256": row["sha256"],
                             "evaluation": key, "reused_from": reused_from})
    analysis = {}
    for suite in ("evaluation", "transfer"):
        comparisons = {"selected_minus_reference": ("selected", "reference"), "selected_minus_incumbent": ("selected", "incumbent")}
        comparisons.update({mode + "_minus_selected": (mode, "selected") for mode in MODES if mode in labels})
        analysis[suite] = {key: paired(evaluations[arm_keys[(suite, left)]], evaluations[arm_keys[(suite, right)]])
                           for key, (left, right) in comparisons.items()}
    public = {"schema_version": 1, "status": "completed", "audit_status": "verified", "model_requested": "gpt-6-sol",
              "source_commit": inputs["source_commit"], "protocol_sha256": safe_hash(inputs["protocol_sha256"]),
              "source_file_sha256": source_map, "source_unchanged": True, "declared_calls": 6, "calls_completed": 6,
              "packet_manifest": {safe_name(k): safe_hash(v) for k, v in inputs.get("packet_manifest", {}).items()},
              "calls": calls, "known_usage": dict(totals), "input_plus_output_tokens": totals["input_tokens"] + totals["output_tokens"],
              "cached_input_and_reasoning_output_are_subsets": True, "development": dev,
              "selection": {"label": selected["label"], "sha256": selected["sha256"], "frozen_at_unix": selected["frozen_at_unix"],
                            "rule": "max_valid_development_earliest_tie", "precedes_all_final_evaluations": True},
              "final": final_public, "unique_final_evaluations": len(seen),
              "unavailable_ablations": [{"intervention": r["intervention"], "status": "unscored", "error_type": safe_code(r.get("error_type"))} for r in unavailable],
              "researcher_wall_seconds": summary.get("elapsed_seconds") if finite(summary.get("elapsed_seconds")) else None,
              "private_summary_sha256": reader.reads[study / "summary.private.json"],
              "limitations": ["One adaptive continuation from a previously selected controller; not an independent researcher sample",
                              "Original evaluation worlds are a regression set; transfer worlds are a new fixed range from the same generator",
                              "Every declared world and invalid trial is retained; incomplete suites have no primary mean",
                              "Natural termination is not task success; reward is not a pass rate",
                              "Descriptive paired differences only; no confidence interval or general model-ranking claim",
                              "Diagnostic wrappers do not isolate pure causal effects; suppression logs are not adversarially secure"]}
    files["summary.json"] = encoded(public)
    files["comparison.json"] = encoded(analysis)
    reader.verify()
    for name, raw in files.items():
        safe_name(name)
        require(not PRIVATE.search(raw.decode("utf-8")), "sensitive_pattern_in_public_export")
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    manifest = {"schema_version": 1, "files": {name: sha(raw) for name, raw in sorted(files.items())},
                "exporter_sha256": sha(Path(__file__).read_bytes()), "automatic_retries": 0,
                "prompts_reasoning_notes_and_private_logs_included": False}
    (output / "MANIFEST.json").write_bytes(encoded(manifest))
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--task", type=Path, default=TASK)
    args = parser.parse_args()
    result = export(args.study, args.output, args.task)
    print(json.dumps({"status": result["audit_status"], "calls_completed": result["calls_completed"],
                      "unique_final_evaluations": result["unique_final_evaluations"]}))


if __name__ == "__main__":
    main()

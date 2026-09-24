"""Synthetic exporter tests. No inference, Docker, candidate imports or rollouts."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import export_extension as exporter
import run_evaluation as runner
import make_ablations
import test_evaluation


class ExportTests(unittest.TestCase):
    def setUp(self):
        fixture = test_evaluation.EvaluationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root, self.task = fixture.root.resolve(), fixture.task.resolve()
        self.study = self.root / "study"
        self.study.mkdir()
        self.output = self.root / "public"
        actual = Path(__file__).resolve().parent
        for name in ("run_evaluation.py", "make_ablations.py"):
            fixture.put(self.task / "paper" / name, (actual / name).read_text())
        fixture.put(self.task / "paper/run_extension.py", "# frozen fixture protocol runner; never executed\n")
        fixture.put(self.task / "paper/EXTENSION-PROTOCOL.md", "Six fixed synthetic calls; NOT a real experiment.\n")
        self.records = []
        self.usage = []
        self.checks = {}

    def candidate(self, label):
        path = self.study / (label.replace("call-", "candidate-") if label.startswith("call-") else label)
        self.fixture.put(path / "controller.py", "# " + label + "\nraise RuntimeError('never execute synthetic candidate')\n")
        return path

    def make_check(self, label, candidate, suite, score=0.4, invalid=False):
        check = self.study / ("check-" + label + "-" + suite)
        manifest = runner.prepare(self.task, self.fixture.source, self.fixture.assets, runner.DEFAULT_IMAGE,
                                  candidate, suite, check)
        (check / "output").mkdir()
        rows = []
        for index, world in enumerate(runner.SUITES[suite]):
            bad = invalid and index == 0
            metrics = {} if bad else {exporter.PRIMARY: score, "Deaths/total_deaths": 3}
            rows.append({"world_id": world, "status": "candidate_invalid" if bad else "scored",
                         "score": None if bad else score, "metrics": metrics, "steps": 10,
                         "trace_sha256": "a" * 64, "naturally_terminated": True,
                         "diagnostic_code": "/Users/private/SHOULD_NOT_EXPORT" if bad else None,
                         "error_type": "sk-proj-SHOULDNOTEXPORT123456789" if bad else None,
                         "private_notes": "sensitive raw field"})
        raw = {"suite": suite, "world_ids": runner.SUITES[suite], "total": len(rows), "cases": rows,
               "scored": len(rows) - int(invalid), "status": "unscored" if invalid else "scored",
               "primary_score": None if invalid else score,
               "metrics_mean": None if invalid else {exporter.PRIMARY: score, "Deaths/total_deaths": 3},
               "host_provenance": {"hashes": runner.expected_hashes(manifest), "proof_first_world": False,
                                   "source_candidate_unchanged": True, "private_path": "/Users/private"},
               "validation_scope": "fixed-full-suite", "provenance_verified": True,
               "infrastructure_affected": False, "reasoning": "DO_NOT_EXPORT_RAW_REASONING"}
        feedback = {"status": raw["status"], "primary_score": raw["primary_score"]}
        runner.dump(check / "output/result.json", raw)
        runner.dump(check / "output/feedback.json", feedback)
        runner.dump(check / "evaluation.json", {"operator_status": "completed", "provenance_verified": True,
                    "candidate_sha256": manifest["candidate_sha256"], "suite": suite,
                    "manifest_sha256": runner.digest(check / "manifest.json"), "primary_score": raw["primary_score"],
                    "result_sha256": runner.digest(check / "output/result.json"),
                    "feedback_sha256": runner.digest(check / "output/feedback.json"),
                    "result_path": "/Users/private/path", "token": "sk-proj-DO_NOT_EXPORT1234567890"})
        runner.dump(check / "operator.private.json", {"returncode": 0, "error_type": None, "cleanup_ok": True,
                    "resources": runner.RESOURCES, "image": {"Id": runner.DEFAULT_IMAGE},
                    "container_state": {"Running": False, "OOMKilled": False, "ExitCode": 0, "StartedAt": "2026-09-24T10:00:00.123456789Z"},
                    "seconds": 1.0, "queue_seconds": 0.1, "command": ["private-host-path"],
                    "stderr": "DO_NOT_EXPORT_RAW_STDERR"})
        self.checks[(label, suite)] = check
        return {"label": label, "candidate": str(candidate), "sha256": manifest["candidate_sha256"],
                "feedback": feedback, "check": str(check)}

    def build_study(self, selected_label="reference", oversized=False):
        for label in exporter.DEVELOPMENT:
            candidate = self.candidate(label)
            score = 0.5 if label == selected_label and label != "reference" else 0.4 if label == "reference" else 0.3
            if oversized and label == "call-01":
                (candidate / "controller.py").write_text("# " + "x" * (1024 * 1024) + "\n")
                check = self.study / "check-call-01-dev"
                check.mkdir()
                feedback = {"status": "unscored", "primary_score": None, "execution_attempted": False,
                            "diagnostic_counts": {"candidate_source_exceeds_1_mib": 1}}
                runner.dump(check / "candidate-invalid.json", feedback)
                row = {"label": label, "candidate": str(candidate), "sha256": runner.digest(candidate / "controller.py"),
                       "feedback": feedback, "check": str(check)}
            else:
                row = self.make_check(label, candidate, "dev", score, invalid=label == "call-01")
            if label in ("reference", "incumbent"):
                row["deployment_parity"] = True
            else:
                call = self.study / label
                call.mkdir()
                tokens = {"input_tokens": 100, "output_tokens": 40, "cached_input_tokens": 20, "reasoning_output_tokens": 30}
                metadata = {"model_requested": "gpt-6-sol", "reasoning_effort": "ultra", "status": "completed",
                            "return_code": 0, "tool_free": True, "seconds": 2.0, "usage": [tokens],
                            "private_path": "/Users/private", "reasoning": "DO_NOT_EXPORT_RAW_REASONING"}
                runner.dump(call / "metadata.json", metadata)
                runner.dump(call / "response.json", {"controller": (candidate / "controller.py").read_text(), "note": "DO_NOT_EXPORT_NOTES /Users/private"})
                self.fixture.put(call / "prompt.txt", "DO_NOT_READ_PROMPT\n")
                self.fixture.put(call / "events.jsonl", "DO_NOT_READ_EVENTS\n")
                self.usage.append({"call": label, "usage": [tokens], "status": "completed", "seconds": 2.0})
            self.records.append(row)
        reference = self.records[0]
        chosen = next(row for row in self.records if row["label"] == selected_label)
        (self.study / "selected").mkdir()
        (self.study / "selected/controller.py").write_bytes(Path(chosen["candidate"]).joinpath("controller.py").read_bytes())
        selected = {"label": selected_label, "sha256": chosen["sha256"], "feedback": chosen["feedback"], "frozen_at_unix": 1}
        runner.dump(self.study / "selection.json", selected)
        ablations = []
        if selected_label != "reference":
            for mode in exporter.MODES:
                path = self.study / ("ablation-" + mode)
                make_ablations.build(self.study / "selected/controller.py", path, mode)
                ablations.append((mode, path))
        final = []
        for suite in ("evaluation", "transfer"):
            new = {}
            for label in ("reference", "incumbent"):
                original = next(r for r in self.records if r["label"] == label)
                row = self.make_check(label, Path(original["candidate"]), suite, 0.4 if label == "reference" else 0.3)
                row.pop("candidate")
                row["suite"] = suite
                final.append(row)
                new[label] = row
            if selected_label == "reference":
                final.append({**new["reference"], "label": "selected", "reused_from": "reference"})
            else:
                row = self.make_check("selected", self.study / "selected", suite, 0.5)
                row.pop("candidate")
                row["suite"] = suite
                final.append(row)
            for mode, path in ablations:
                row = self.make_check(mode, path, suite, 0.2)
                row.pop("candidate")
                row["suite"] = suite
                final.append(row)
        summary = {"status": "completed", "phase": "complete", "source_unchanged": True,
                   "calls_attempted": 6, "declared_calls": 6, "model_requested": "gpt-6-sol", "records": self.records,
                   "usage": {"usage_complete": True, "calls": self.usage,
                             "known_usage": {"input_tokens": 600, "output_tokens": 240, "cached_input_tokens": 120, "reasoning_output_tokens": 180},
                             "input_plus_output_tokens": 840}, "selected": selected, "final": final,
                   "ablation_status": "not_run_selected_pass_through", "elapsed_seconds": 100,
                   "reasoning": "DO_NOT_EXPORT_RAW_REASONING", "notes": "DO_NOT_EXPORT_NOTES"}
        runner.dump(self.study / "summary.private.json", summary)
        tracked = [self.task / "native" / name for name in runner.NATIVE]
        tracked += [self.task / "controller" / name for name in runner.CONTROLLER]
        tracked += [self.task / "paper" / name for name in ("run_evaluation.py", "run_extension.py", "make_ablations.py", "EXTENSION-PROTOCOL.md")]
        tracked += [self.task / "baseline" / name for name in ("source-manifest.json", "asset-manifest.json")]
        tracked += [self.task / "TASK_DESIGN.md"]
        transport = self.task.parent / "relayrepair/pilot/codex_runner.py"
        self.fixture.put(transport, "# Frozen synthetic transport. Never executed.\n")
        tracked.append(transport)
        packet = self.root / "packet"
        self.fixture.put(packet / "public.txt", "Synthetic public packet content.\n")
        packet_manifest = {"public.txt": runner.digest(packet / "public.txt")}
        runner.dump(packet / "MANIFEST.json", packet_manifest)
        tracked += [packet / "public.txt", packet / "MANIFEST.json"]
        parity = {}
        for label in ("reference", "incumbent"):
            path = self.root / ("old-" + label + "-dev.json")
            path.write_bytes((self.checks[(label, "dev")] / "output/result.json").read_bytes())
            tracked.append(path)
            parity[label] = runner.digest(path)
        for attribute, value in (("PARITY_SHAS", parity), ("SOL_SHA", self.records[1]["sha256"]),
                                 ("PACKET_SHA", runner.digest(packet / "MANIFEST.json"))):
            patcher = patch.object(exporter, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Capture trusted bytes before a test can mutate files and their manifests.
        committed = {exporter.TASK_REPO_PATH + "/" + path.relative_to(self.task).as_posix(): path.read_bytes()
                     for path in tracked if path.is_relative_to(self.task)}
        committed[exporter.TRANSPORT_REPO_PATH] = transport.read_bytes()
        patcher = patch.object(exporter, "read_committed_blob", side_effect=lambda repo, name: committed[name])
        patcher.start()
        self.addCleanup(patcher.stop)
        inputs = {"files": {str(p): runner.digest(p) for p in tracked}, "declared_calls": 6,
                  "model_requested": "gpt-6-sol", "reasoning_effort": "ultra", "fresh_worlds": runner.SUITES["transfer"],
                  "original_worlds": runner.SUITES["evaluation"], "source_commit": exporter.SOURCE_COMMIT,
                  "starting_sol_sha256": self.records[1]["sha256"],
                  "protocol_sha256": runner.digest(self.task / "paper/EXTENSION-PROTOCOL.md"), "packet_manifest": packet_manifest}
        runner.dump(self.study / "study-inputs.json", inputs)
        return summary

    def test_end_to_end_preserves_invalid_all_worlds_reuse_tokens_and_privacy(self):
        self.build_study()
        result = exporter.export(self.study, self.output, self.task)
        self.assertEqual(result["calls_completed"], 6)
        self.assertEqual(result["input_plus_output_tokens"], 840)
        self.assertEqual(result["unique_final_evaluations"], 4)
        self.assertEqual(len(result["development"]), 8)
        self.assertEqual(result["development"][2]["status"], "unscored")
        self.assertEqual(sum(r["reused_from"] == "reference" for r in result["final"]), 2)
        dev = json.loads((self.output / "evaluations/dev-call-01.json").read_text())
        self.assertEqual(len(dev["worlds"]), 4)
        self.assertIsNone(dev["primary_score"])
        self.assertEqual(dev["worlds"][0]["diagnostic_code"], "other")
        comparison = json.loads((self.output / "comparison.json").read_text())
        self.assertEqual(comparison["transfer"]["selected_minus_reference"]["equal"], 20)
        self.assertAlmostEqual(comparison["transfer"]["selected_minus_incumbent"]["mean_difference"], 0.1)
        for path in self.output.rglob("*"):
            if path.is_file():
                text = path.read_text()
                self.assertNotRegex(text, exporter.PRIVATE)
                self.assertNotIn("DO_NOT_", text)
                self.assertNotIn("private-host-path", text)
        manifest = json.loads((self.output / "MANIFEST.json").read_text())
        self.assertTrue(all(exporter.sha((self.output / name).read_bytes()) == digest for name, digest in manifest["files"].items()))
        with self.assertRaisesRegex(ValueError, "output_directory_exists"):
            exporter.export(self.study, self.output, self.task)

    def test_extra_call_and_token_subset_are_rejected(self):
        self.build_study()
        (self.study / "call-07").mkdir()
        with self.assertRaisesRegex(ValueError, "generation_directory_inventory_mismatch"):
            exporter.export(self.study, self.output, self.task)
        (self.study / "call-07").rmdir()
        path = self.study / "call-01/metadata.json"
        value = json.loads(path.read_text())
        value["usage"][0]["reasoning_output_tokens"] = 41
        runner.dump(path, value)
        with self.assertRaisesRegex(ValueError, "token_subset_exceeds_parent"):
            exporter.export(self.study, self.output, self.task)
        self.assertFalse(self.output.exists())

    def test_changed_candidate_is_rejected_without_import(self):
        self.build_study()
        path = self.study / "candidate-03/controller.py"
        path.write_text("raise RuntimeError('must not execute')\n")
        with self.assertRaisesRegex(ValueError, "input_hash_mismatch"):
            exporter.export(self.study, self.output, self.task)

    def test_coherent_repository_and_recorded_hash_tampering_fails_before_helper_execution(self):
        self.build_study()
        inputs_path = self.study / "study-inputs.json"
        original_inputs = inputs_path.read_bytes()
        sentinel = self.root / "HELPER_EXECUTED"
        for relative in ("paper/run_evaluation.py", "baseline/asset-manifest.json"):
            with self.subTest(relative=relative):
                target = self.task / relative
                original = target.read_bytes()
                if relative.endswith(".py"):
                    target.write_text("from pathlib import Path\nPath(" + repr(str(sentinel)) + ").touch()\n" + original.decode())
                else:
                    value = json.loads(original)
                    value["revision"] = "f" * 40
                    runner.dump(target, value)
                inputs = json.loads(original_inputs)
                inputs["files"][str(target)] = runner.digest(target)
                runner.dump(inputs_path, inputs)
                with self.assertRaisesRegex(ValueError, "repository_input_differs_from_frozen_commit"):
                    exporter.export(self.study, self.output, self.task)
                self.assertFalse(sentinel.exists())
                self.assertFalse(self.output.exists())
                target.write_bytes(original)
                inputs_path.write_bytes(original_inputs)

    def test_coherent_packet_and_manifest_tampering_fails_fixed_anchor(self):
        self.build_study()
        packet = self.root / "packet"
        (packet / "public.txt").write_text("Different research instructions.\n")
        manifest = {"public.txt": runner.digest(packet / "public.txt")}
        runner.dump(packet / "MANIFEST.json", manifest)
        path = self.study / "study-inputs.json"
        inputs = json.loads(path.read_text())
        inputs["packet_manifest"] = manifest
        for name in ("public.txt", "MANIFEST.json"):
            inputs["files"][str(packet / name)] = runner.digest(packet / name)
        runner.dump(path, inputs)
        with self.assertRaisesRegex(ValueError, "fixed_packet_manifest_missing_or_ambiguous"):
            exporter.export(self.study, self.output, self.task)

    def test_fabricated_unavailable_ablation_is_rejected(self):
        summary = self.build_study(selected_label="call-06")
        mode = exporter.MODES[0]
        summary["unavailable_ablations"] = [{"intervention": mode, "status": "unscored", "error_type": "ValueError"}]
        summary["final"] = [row for row in summary["final"] if row["label"] != mode]
        runner.dump(self.study / "summary.private.json", summary)
        with self.assertRaisesRegex(ValueError, "available_ablation_cannot_be_omitted"):
            exporter.export(self.study, self.output, self.task)

    def test_invalid_suite_cannot_publish_partial_metric_means(self):
        self.build_study()
        check = self.checks[("call-01", "dev")]
        path = check / "output/result.json"
        value = json.loads(path.read_text())
        value["metrics_mean"] = {exporter.PRIMARY: 0.3, "Deaths/total_deaths": 3}
        runner.dump(path, value)
        audit = json.loads((check / "evaluation.json").read_text())
        audit["result_sha256"] = runner.digest(path)
        runner.dump(check / "evaluation.json", audit)
        with self.assertRaisesRegex(ValueError, "incomplete_suite_has_aggregate_metrics"):
            exporter.export(self.study, self.output, self.task)

    def test_response_bytes_must_match_evaluated_candidate(self):
        self.build_study()
        path = self.study / "call-03/response.json"
        response = json.loads(path.read_text())
        response["controller"] += "# silently changed response\n"
        runner.dump(path, response)
        with self.assertRaisesRegex(ValueError, "model_response_candidate_bytes_mismatch"):
            exporter.export(self.study, self.output, self.task)

    def test_ablations_are_exact_and_compared_without_inventing_missing_counts(self):
        self.build_study(selected_label="call-06")
        result = exporter.export(self.study, self.output, self.task)
        self.assertEqual(result["unique_final_evaluations"], 10)
        comparison = json.loads((self.output / "comparison.json").read_text())
        self.assertAlmostEqual(comparison["transfer"][exporter.MODES[0] + "_minus_selected"]["mean_difference"], -0.3)
        suppression = json.loads((self.output / ("evaluations/transfer-" + exporter.MODES[1] + ".json")).read_text())["suppression_diagnostic"]
        self.assertEqual(suppression["status"], "unknown")
        self.assertIsNone(suppression["count"])

    def test_oversized_invalid_candidate_retained_without_execution(self):
        self.build_study(oversized=True)
        result = exporter.export(self.study, self.output, self.task)
        row = result["development"][2]
        self.assertIsNone(row["primary_score"])
        self.assertGreater((self.output / row["candidate_file"]).stat().st_size, 1024 * 1024)
        check = json.loads((self.output / "evaluations/dev-call-01.json").read_text())
        self.assertFalse(check["execution_attempted"])
        self.assertEqual(len(check["worlds"]), 4)

    def test_missing_world_and_repaired_metadata_cannot_hide_it(self):
        self.build_study()
        check = self.checks[("incumbent", "transfer")]
        path = check / "output/result.json"
        value = json.loads(path.read_text())
        value["cases"].pop()
        runner.dump(path, value)
        audit = json.loads((check / "evaluation.json").read_text())
        audit["result_sha256"] = runner.digest(path)
        runner.dump(check / "evaluation.json", audit)
        with self.assertRaisesRegex(ValueError, "native_result_validation_failed"):
            exporter.export(self.study, self.output, self.task)

    def test_completed_flag_does_not_override_selection_rule(self):
        summary = self.build_study()
        selected = {"label": "incumbent", "sha256": self.records[1]["sha256"], "feedback": self.records[1]["feedback"]}
        summary["selected"] = selected
        runner.dump(self.study / "summary.private.json", summary)
        runner.dump(self.study / "selection.json", selected)
        with self.assertRaisesRegex(ValueError, "selection_rule_mismatch"):
            exporter.export(self.study, self.output, self.task)

    def test_incomplete_study_refused(self):
        self.build_study()
        path = self.study / "summary.private.json"
        value = json.loads(path.read_text())
        value.update(status="incomplete", calls_attempted=2)
        runner.dump(path, value)
        with self.assertRaisesRegex(ValueError, "study_not_complete_six_calls"):
            exporter.export(self.study, self.output, self.task)

    def test_suppression_count_requires_full_untruncated_byte_inventory(self):
        check = self.root / "logs"
        (check / "output").mkdir(parents=True)
        traffic = []
        for actor in range(3):
            raw = exporter.MARKER + b"\n" if actor == 1 else b""
            (check / "output" / f"world-30000-actor-{actor}.stderr.txt").write_bytes(raw)
            traffic.append({"stderr_bytes": len(raw), "stderr_truncated": False})
        traffic.append({"stderr_bytes": 9, "stderr_truncated": False})
        launch = {"process_traffic": traffic, "source_candidate_unchanged": True}
        runner.dump(check / "output/launch.private.json", launch)
        raw = {"status": "scored", "world_ids": [30000]}
        count = exporter.suppression_count(exporter.Reader(), check, raw)
        self.assertEqual(count["status"], "complete")
        self.assertEqual(count["count"], 1)
        launch["process_traffic"][1]["stderr_truncated"] = True
        runner.dump(check / "output/launch.private.json", launch)
        count = exporter.suppression_count(exporter.Reader(), check, raw)
        self.assertEqual(count["status"], "unknown")
        self.assertIsNone(count["count"])

    def test_partial_paired_difference_has_no_summary_mean(self):
        left = {"world_ids": [1, 2], "worlds": [{"world_id": 1, "status": "scored", "score": 0.5},
                  {"world_id": 2, "status": "candidate_invalid", "score": None}]}
        right = {"world_ids": [1, 2], "worlds": [{"world_id": 1, "status": "scored", "score": 0.2},
                   {"world_id": 2, "status": "scored", "score": 0.2}]}
        result = exporter.paired(left, right)
        self.assertEqual(len(result["worlds"]), 2)
        self.assertEqual(result["valid_pairs"], 1)
        self.assertIsNone(result["mean_difference"])


if __name__ == "__main__":
    unittest.main()

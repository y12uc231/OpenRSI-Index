"""Mocked CPU-diagnostic control-flow checks: no Docker, model calls or games."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import export_extension as audit
import run_evaluation as evaluator
import run_trajectory_diagnostic as diagnostic


class Reader:
    def __init__(self):
        self.reads = {}
        self.verifications = 0

    def verify(self):
        self.verifications += 1


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.output = self.root / "diagnostic"
        self.output.mkdir()

    def context(self, *, duplicate=False, infrastructure=False, invalid=False, oversized=False):
        candidates = []
        for i, label in enumerate(diagnostic.CALLS):
            path = self.output / "candidates" / label
            path.mkdir(parents=True)
            code = "# fixture " + str(0 if duplicate and i == 1 else i)
            if oversized and i == 0:
                code += "x" * (evaluator.MAX_CANDIDATE + 1)
            (path / "controller.py").write_text(code)
            candidates.append({"label": label, "sha256": diagnostic.sha(path / "controller.py"),
                               "bytes": len(code.encode()), "candidate": str(path),
                               "development_status": "scored", "development_score": 0.2})
        calls = []

        def evaluate(*args, **kwargs):
            calls.append((args, kwargs))
            return {"operator_status": "infrastructure_or_incomplete" if infrastructure else "completed",
                    "provenance_verified": not infrastructure, "seconds": 1, "primary_score": None if invalid else 0.3}

        def result(reader, check, suite, candidate_hash, task, inputs, helper):
            candidate = {"sha256": candidate_hash}
            if invalid:
                return diagnostic.unscored_result(audit, candidate, suite, "candidate_invalid", "candidate_act", True)
            return {"suite": suite, "world_ids": audit.SUITES[suite], "total": 20, "status": "scored", "scored": 20,
                    "primary_score": 0.3, "candidate_sha256": candidate_hash, "metrics_mean": {audit.PRIMARY: 0.3},
                    "worlds": [{"world_id": w, "status": "scored", "score": 0.3, "metrics": {audit.PRIMARY: 0.3}}
                               for w in audit.SUITES[suite]]}

        helper = SimpleNamespace(evaluate=evaluate, RESOURCES=evaluator.RESOURCES, DEFAULT_IMAGE=evaluator.DEFAULT_IMAGE,
                                 MAX_CANDIDATE=evaluator.MAX_CANDIDATE)
        reader = Reader()
        fake_audit = SimpleNamespace(require=audit.require, SUITES=audit.SUITES, evaluation=result)
        context = {"audit": fake_audit, "reader": reader, "helper": helper, "inputs": {},
                   "main_public": {"selection": {"label": "reference", "sha256": "a" * 64}},
                   "main_study": self.root / "main", "task": self.root / "task", "source_identity": {"fixture": "b" * 64},
                   "timing": {"declaration_precedes_selection_freeze": True}, "declaration": diagnostic.DECLARATION,
                   "candidates": candidates, "cache": {}}
        return context, calls, result

    def matrix(self, context):
        return diagnostic.run_matrix(context, self.output, self.root / "source", self.root / "assets", self.root / "shared.lock")

    def test_all_twelve_fields_and_strict_timeout_without_model_calls(self):
        context, calls, _ = self.context()
        result = self.matrix(context)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["fields"]), 12)
        self.assertEqual(len(calls), 12)
        self.assertEqual(result["additional_inference_calls"], 0)
        self.assertEqual(result["automatic_retries"], 0)
        self.assertTrue(all(kwargs == {"timeout": 10800} for _, kwargs in calls))
        self.assertTrue(all(args[3] == evaluator.DEFAULT_IMAGE and args[7] == self.root / "shared.lock" for args, _ in calls))
        self.assertTrue(result["source_unchanged"])

    def test_exact_hash_and_suite_reuse_from_main_and_prior_diagnostic(self):
        context, calls, public_result = self.context(duplicate=True)
        first = context["candidates"][0]
        context["cache"][("evaluation", first["sha256"])] = {
            "origin": "main", "label": "incumbent", "suite": "evaluation", "check": "/prior/check",
            "public_result": public_result(None, None, "evaluation", first["sha256"], None, None, None)}
        result = self.matrix(context)
        self.assertEqual(len(calls), 9)
        self.assertEqual(result["reused_fields"], 3)
        self.assertEqual(result["fields"][0]["reused_from"]["origin"], "main")
        self.assertEqual(result["fields"][1]["reused_from"]["origin"], "main")
        self.assertEqual(result["fields"][7]["reused_from"], {"origin": "diagnostic", "label": "call-01", "suite": "transfer"})

    def test_infrastructure_stops_without_retry_and_retains_remaining_fields(self):
        context, calls, _ = self.context(infrastructure=True)
        result = self.matrix(context)
        self.assertEqual(result["status"], "unscored_infrastructure")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["fields"][0]["state"], "infrastructure_or_incomplete")
        self.assertTrue(all(f["state"] == "not_run" for f in result["fields"][1:]))
        self.assertTrue(all(f["result"]["primary_score"] is None and len(f["result"]["worlds"]) == 20 for f in result["fields"]))

    def test_semantically_invalid_candidates_are_retained_and_do_not_stop(self):
        context, calls, _ = self.context(invalid=True)
        result = self.matrix(context)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(calls), 12)
        self.assertTrue(all(f["state"] == "evaluated" and f["result"]["primary_score"] is None for f in result["fields"]))

    def test_oversized_source_is_unscored_without_execution_on_both_suites(self):
        context, calls, _ = self.context(oversized=True)
        result = self.matrix(context)
        self.assertEqual(len(calls), 10)
        self.assertEqual(result["skipped_invalid_fields"], 2)
        self.assertTrue(all(result["fields"][i]["state"] == "candidate_invalid_without_execution" for i in (0, 6)))

    def test_exception_preserves_failure_and_does_not_retry(self):
        context, calls, _ = self.context()
        context["helper"].evaluate = Mock(side_effect=RuntimeError("private details should not be copied"))
        result = self.matrix(context)
        self.assertEqual(context["helper"].evaluate.call_count, 1)
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertEqual(result["status"], "unscored_infrastructure")
        self.assertEqual(result["fields"][0]["result"]["worlds"][0]["diagnostic_code"], "evaluation_infrastructure")
        self.assertNotIn("private details", (self.output / "summary.private.json").read_text())

    def test_export_accounting_recomputes_requests_reuse_and_skips(self):
        context, _, _ = self.context(duplicate=True)
        result = self.matrix(context)
        self.assertEqual(diagnostic.validate_matrix_accounting(audit, result),
                         {"evaluation_requests": 10, "reused_fields": 2, "skipped_invalid_fields": 0})
        for key in ("evaluation_requests", "reused_fields", "skipped_invalid_fields"):
            with self.subTest(counter=key):
                changed = json.loads(json.dumps(result))
                changed[key] += 1
                with self.assertRaisesRegex(ValueError, "diagnostic_counter_mismatch"):
                    diagnostic.validate_matrix_accounting(audit, changed)

    def test_export_rejects_evaluation_after_unattempted_field(self):
        context, _, _ = self.context()
        result = self.matrix(context)
        result["status"] = "unscored_infrastructure"
        result["fields"][0]["state"] = "not_run"
        result["evaluation_requests"] = 11
        with self.assertRaisesRegex(ValueError, "evaluation_after_infrastructure_stop"):
            diagnostic.validate_matrix_accounting(audit, result)

    def test_export_accepts_terminal_unattempted_tail_but_not_completed_label(self):
        context, _, _ = self.context(infrastructure=True)
        result = self.matrix(context)
        self.assertEqual(diagnostic.validate_matrix_accounting(audit, result)["evaluation_requests"], 1)
        # A verification failure before a request can leave the entire matrix
        # untouched. It is retained with zero requests, never called completed.
        result["fields"][0]["state"] = "not_run"
        result["evaluation_requests"] = 0
        self.assertEqual(diagnostic.validate_matrix_accounting(audit, result)["evaluation_requests"], 0)
        result["status"] = "completed"
        with self.assertRaisesRegex(ValueError, "incomplete_field_in_completed_diagnostic"):
            diagnostic.validate_matrix_accounting(audit, result)

    def test_timing_rejects_declaration_after_selection_or_any_final(self):
        declared = diagnostic.DECLARATION["declared_at_unix"]
        main = self.root / "main"
        summary = {"selected": {"frozen_at_unix": declared + 1}, "final": [{"check": str(main / "check-final")}]}
        reader = SimpleNamespace(obj=lambda *args, **kwargs: {"container_state": {
            "StartedAt": datetime.fromtimestamp(declared + 2, timezone.utc).isoformat().replace("+00:00", "Z")}})
        result = diagnostic.validate_timing(audit, reader, main, summary, diagnostic.DECLARATION)
        self.assertTrue(result["declaration_precedes_every_main_final_start"])
        summary["selected"]["frozen_at_unix"] = declared - 1
        with self.assertRaisesRegex(ValueError, "declaration_did_not_precede_selection_freeze"):
            diagnostic.validate_timing(audit, reader, main, summary, diagnostic.DECLARATION)
        summary["selected"]["frozen_at_unix"] = declared + 1
        reader.obj = lambda *args, **kwargs: {"container_state": {"StartedAt": "2020-01-01T00:00:00Z"}}
        with self.assertRaisesRegex(ValueError, "main_final_started_before_diagnostic_declaration"):
            diagnostic.validate_timing(audit, reader, main, summary, diagnostic.DECLARATION)

    def test_existing_output_refused_before_preflight(self):
        with patch.object(diagnostic, "prepare_context", side_effect=AssertionError("must not run")):
            with self.assertRaises(FileExistsError):
                diagnostic.run(self.root / "main", self.output, self.root / "source", self.root / "assets",
                               self.root / "lock", self.root / "declaration")


if __name__ == "__main__":
    unittest.main()

"""Synthetic-record tests; never execute candidate source or Docker."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from package_integrity import ROOT, digest, read_json, validate_published
from validate_results import validate


class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provenance = read_json(ROOT / "PROVENANCE.json")
        cls.hashes = {role: "0" * 64 for role in ("db", "api", "consumer")}
        # These are deliberately synthetic envelopes, using already-published
        # trusted-control result objects only as schema fixtures. They never
        # become performance evidence or persist outside TemporaryDirectory.
        rows = read_json(ROOT / "results/trusted-controls.json")["cases"]
        cls.records = [{"index": row["index"],
                        "split": "calibration" if row["index"] < 4 else "evaluation",
                        "candidate_sha256": cls.hashes,
                        "seal_sha256": cls.provenance["original_seal_sha256"],
                        "runner_sha256": cls.provenance["original_replay_runner_sha256"],
                        "source_verified": True, "model_calls": 0,
                        "result": row["result"]}
                       for row in rows if row["control"] == "reference"]

    def write(self, directory, records):
        for i, record in enumerate(records):
            (directory / f"case-{i:02d}.json").write_text(json.dumps(record))

    def test_normative_hash_links_and_historical_records(self):
        result = validate_published()
        self.assertEqual(result["generated_cases"], 20)
        self.assertEqual(result["candidate_executions"], 0)

    def test_complete_original_wrapper_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write(path, self.records)
            result = validate(path, self.hashes)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["evaluation"]["records"], 16)

    def test_missing_record_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write(path, self.records[:-1])
            with self.assertRaisesRegex(ValueError, "incomplete pack"):
                validate(path, self.hashes)
            result = validate(path, self.hashes, allow_incomplete=True)
            self.assertEqual(result["missing_indices"], [19])
            self.assertEqual(result["status"], "incomplete")

    def test_duplicate_and_wrong_seed_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write(path, self.records + [self.records[0]])
            with self.assertRaisesRegex(ValueError, "repeated case"):
                validate(path, self.hashes)
        with tempfile.TemporaryDirectory() as directory:
            records = copy.deepcopy(self.records)
            records[0]["result"]["schedule_audit"]["config"]["seed"] = "1" * 64
            path = Path(directory)
            self.write(path, records)
            with self.assertRaisesRegex(ValueError, "different seeded case"):
                validate(path, self.hashes)

    def test_unscored_and_failed_outcomes_are_retained(self):
        records = copy.deepcopy(self.records)
        statuses = ("candidate_invalid", "unscored_audit_bound", "unscored_checker_bound", "infrastructure_or_incomplete")
        for record, status in zip(records, statuses):
            record["result"].update(status=status, score=None, passed=False)
        records[4]["result"].update(score=0.0, passed=False)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write(path, records)
            result = validate(path, self.hashes)
            self.assertEqual(result["all"]["records"], 20)
            self.assertEqual(result["all"]["unscored"], 4)
            self.assertEqual(result["all"]["scored"], 16)
            self.assertEqual(result["all"]["passed"], 15)

    def test_new_wrapper_binds_package_manifest(self):
        records = copy.deepcopy(self.records)
        for record in records:
            record["runner_sha256"] = digest(ROOT / "replay.py")
            record["package_manifest_sha256"] = digest(ROOT / "PACKAGE-SHA256.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write(path, records)
            self.assertEqual(validate(path, self.hashes)["status"], "complete")
            records[0]["package_manifest_sha256"] = "f" * 64
            self.write(path, records)
            with self.assertRaisesRegex(ValueError, "manifest mismatch"):
                validate(path, self.hashes)

    def test_wrong_candidate_or_invalid_score_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write(path, self.records)
            wrong = self.hashes | {"db": "f" * 64}
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                validate(path, wrong)
            records = copy.deepcopy(self.records)
            records[0]["result"].update(score=None)
            self.write(path, records)
            with self.assertRaisesRegex(ValueError, "inconsistent scored"):
                validate(path, self.hashes)

    def test_replay_passes_external_invoker_without_importing_candidate(self):
        import replay
        token = object()
        invoker = mock.MagicMock()
        invoker.__enter__.return_value = token
        constructor = mock.Mock(return_value=invoker)
        execute = mock.Mock(return_value={"status": "scored", "score": 1.0, "passed": True})
        modules = {"runtime": SimpleNamespace(execute=execute),
                   "scenarios": SimpleNamespace(make_case=lambda index: {"index": index}),
                   "isolated": SimpleNamespace(MultiStoreInvoker=constructor, PINNED_IMAGE="test-only-placeholder")}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = (root / "candidate").resolve()
            candidate.mkdir()
            for role in self.hashes:
                (candidate / (role + ".py")).write_text("raise AssertionError('must never import on host')\n")
            output = root / "result.json"
            args = ["replay.py", "--candidate", str(candidate), "--index", "3", "--output", str(output)]
            with mock.patch("sys.argv", args), mock.patch.object(replay, "trusted_modules", return_value=modules), mock.patch("builtins.print"):
                replay.main()
            constructor.assert_called_once_with(candidate, legacy_helper=ROOT / "task/reference/immutable_v1.py")
            execute.assert_called_once_with(candidate, {"index": 3}, invoke=token)
            self.assertEqual(read_json(output)["runner_kind"], "portable_public_packaging_v1")
            self.assertEqual(read_json(output)["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()

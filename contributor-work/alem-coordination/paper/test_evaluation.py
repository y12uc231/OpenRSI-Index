"""Offline boundary checks only. No candidate imports, Docker runs, or rollouts."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run_evaluation as runner


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = self.root / "task"
        self.source = self.root / "source"
        self.assets = self.root / "assets"
        self.candidate = self.root / "candidate"
        self.output = self.root / "prepared"
        self.lock = self.root / "evaluation.lock"
        actual = Path(__file__).resolve().parents[1]
        self.put(self.source / "alem/__init__.py", "# never imported\n")
        self.put(self.assets / "fixture/checkpoint", "fake checkpoint; not a model\n")
        self.put(self.candidate / "controller.py", "raise RuntimeError('must never import candidate on host')\n")
        self.put(self.candidate / "secret.txt", "not mounted\n")
        self.put(self.task / "results/private.json", "do not copy\n")
        self.put(self.task / "native/evidence/expected.json", "do not copy\n")
        self.put(self.task / ".git/config", "do not copy\n")
        for name in runner.NATIVE:
            self.put(self.task / "native" / name, (actual / "native" / name).read_text())
        for name in runner.CONTROLLER:
            self.put(self.task / "controller" / name, (actual / "controller" / name).read_text())
        self.put(self.task / "TASK_DESIGN.md", "Public task description.\n")
        self.write_manifests()

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def write_manifests(self):
        (self.task / "baseline").mkdir(parents=True)
        runner.dump(self.task / "baseline/source-manifest.json", {
            "revision": runner.SOURCE_REVISION,
            "files": {"alem/__init__.py": runner.digest(self.source / "alem/__init__.py")}})
        path = self.assets / "fixture/checkpoint"
        runner.dump(self.task / "baseline/asset-manifest.json", {
            "revision": runner.ASSET_REVISION,
            "files": [{"path": "assets/fixture/checkpoint", "bytes": path.stat().st_size,
                       "sha256": runner.digest(path)}]})

    def prepare(self, suite="dev"):
        return runner.prepare(self.task, self.source, self.assets, runner.DEFAULT_IMAGE,
                              self.candidate, suite, self.output)

    def result(self, manifest, invalid=False):
        rows = [{"world_id": world, "status": "scored", "score": (i + 1) / 10,
                 "metrics": {runner.METRIC: (i + 1) / 10}}
                for i, world in enumerate(manifest["world_ids"])]
        if invalid:
            rows[0].update(status="candidate_invalid", score=None, metrics={})
        mean = None if invalid else sum(row["score"] for row in rows) / len(rows)
        return {"suite": manifest["suite"], "world_ids": manifest["world_ids"], "total": len(rows),
                "cases": rows, "scored": len(rows) - int(invalid), "status": "unscored" if invalid else "scored",
                "primary_score": mean, "metrics_mean": None if invalid else {runner.METRIC: mean},
                "host_provenance": {"hashes": runner.expected_hashes(manifest), "proof_first_world": False,
                                    "source_candidate_unchanged": True},
                "validation_scope": "fixed-full-suite", "provenance_verified": True,
                "infrastructure_affected": False}

    def docker_mock(self, manifest, *, invalid=False, timeout=False):
        calls = []

        def invoke(command, **kwargs):
            calls.append(command)
            if command[:3] == ["docker", "image", "inspect"]:
                return subprocess.CompletedProcess(command, 0, json.dumps([{
                    "Id": runner.DEFAULT_IMAGE, "Architecture": "arm64", "Os": "linux"}]))
            if command[:2] == ["docker", "run"]:
                if timeout:
                    raise subprocess.TimeoutExpired(command, 1)
                runner.dump(self.output / "output/result.json", self.result(manifest, invalid=invalid))
                runner.dump(self.output / "output/feedback.json", {"mock": True})
                return subprocess.CompletedProcess(command, 0)
            if command[:2] == ["docker", "inspect"]:
                state = {"Running": timeout, "OOMKilled": False, "ExitCode": 0}
                return subprocess.CompletedProcess(command, 0, json.dumps([{"State": state}]))
            if command[:3] == ["docker", "rm", "--force"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            raise AssertionError(command)
        return invoke, calls

    def test_prepare_never_executes_and_excludes_unlisted_inputs(self):
        with patch.object(runner.subprocess, "run", side_effect=AssertionError("execution during prepare")):
            manifest = self.prepare()
        self.assertEqual(manifest["candidate_sha256"], runner.digest(self.candidate / "controller.py"))
        self.assertEqual(set(n for n in manifest["files"] if n.startswith("candidate/")), {"candidate/controller.py"})
        self.assertFalse(any({"results", "evidence", ".git", "secret.txt"}.intersection(Path(n).parts)
                             for n in manifest["files"]))
        self.assertEqual(manifest["files"], manifest["original_files"])
        self.assertEqual((self.output / "transfer.patch").read_text(), "")
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_source_hash_and_path_escape_rejected(self):
        self.put(self.source / "alem/__init__.py", "changed source\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.prepare()
        for name in ("../candidate/controller.py", "/etc/passwd"):
            with self.assertRaises(ValueError):
                runner.regular(self.source, name)

    def test_symlinks_rejected_in_source_and_candidate(self):
        original = self.source / "alem/__init__.py"
        original.unlink()
        original.symlink_to(self.candidate / "controller.py")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.prepare()
        alias = self.root / "candidate-alias"
        alias.symlink_to(self.candidate, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "real directory"):
            runner.regular(alias, "controller.py")

    def test_transfer_only_changes_world_dispatch_and_preserves_production(self):
        originals = {name: (self.task / "native" / name).read_bytes() for name in runner.NATIVE}
        manifest = self.prepare("transfer")
        changed = {n for n, digest in manifest["files"].items() if digest != manifest["original_files"][n]}
        self.assertEqual(changed, {"task/native/run.py", "task/native/engine.py"})
        self.assertEqual(manifest["world_ids"], list(range(30000, 30020)))
        self.assertIn("independent-paper", manifest["scientific_scope"])
        for name, expected in originals.items():
            self.assertEqual((self.task / "native" / name).read_bytes(), expected)
        engine = (self.output / "stage/task/native/engine.py").read_text()
        unadapted = engine.replace("choices=('dev','evaluation','transfer')", "choices=('dev','evaluation')").replace(
            "worlds={'dev':list(range(20000,20004)), 'evaluation':list(range(9999,10019)), 'transfer':list(range(30000,30020))}[args.suite]",
            "worlds=list(range(20000,20004)) if args.suite=='dev' else list(range(9999,10019))")
        self.assertEqual(unadapted.encode(), originals["engine.py"])

    def test_transfer_drift_fails_closed(self):
        path = self.task / "native/engine.py"
        self.put(path, path.read_text().replace("choices=('dev','evaluation')", "choices=('unknown',)"))
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            self.prepare("transfer")

    def test_docker_boundary_and_fixed_resources(self):
        manifest = self.prepare()
        cmd = runner.docker_command(self.output, manifest, "test-name")
        self.assertEqual(cmd[cmd.index("--network") + 1], "none")
        self.assertEqual(cmd[cmd.index("--cpus") + 1], "4")
        self.assertEqual(cmd[cmd.index("--memory") + 1], "16g")
        self.assertEqual(cmd[cmd.index("--pids-limit") + 1], "256")
        mounts = [cmd[i+1] for i, arg in enumerate(cmd) if arg == "--mount"]
        self.assertEqual(len(mounts), 5)
        self.assertEqual(sum(m.endswith(",readonly") for m in mounts), 4)
        self.assertTrue(mounts[-1].endswith("dst=/results"))
        self.assertFalse(any("docker.sock" in m or "/research/" in m for m in mounts))
        self.assertNotIn("--privileged", cmd)
        self.assertNotIn("--cap-add", cmd)
        self.assertIn("OMP_NUM_THREADS=4", cmd)
        self.assertIn("--pull=never", cmd)
        self.assertEqual(cmd[cmd.index("python"):cmd.index("python") + 4], ["python", "-I", "-B", "/task/native/run.py"])

    def test_scores_require_complete_inventory_and_exact_artifact_hashes(self):
        manifest = self.prepare()
        result = self.result(manifest)
        self.assertEqual(runner.validate_result(result, manifest), ([], 0.25))
        result["cases"] = result["cases"][:-1]
        self.assertEqual(runner.validate_result(result, manifest)[0], ["world_inventory_mismatch"])
        result = self.result(manifest)
        result["host_provenance"]["hashes"]["candidate_sha256"] = "0" * 64
        self.assertIn("artifact_hash_mismatch", runner.validate_result(result, manifest)[0])

    def test_invalid_world_is_unscored_not_dropped_or_zero(self):
        manifest = self.prepare()
        result = self.result(manifest, invalid=True)
        self.assertEqual(runner.validate_result(result, manifest), ([], None))
        result["primary_score"] = 0.3
        self.assertIn("partial_suite_has_primary_score", runner.validate_result(result, manifest)[0])
        result = self.result(manifest)
        result["cases"][0]["metrics"][runner.METRIC] = True
        self.assertIn("invalid_world_score", runner.validate_result(result, manifest)[0])

    def test_world_infrastructure_failure_stops_even_after_clean_engine_exit(self):
        manifest = self.prepare()
        result = self.result(manifest, invalid=True)
        result["cases"][0]["status"] = "infrastructure_or_incomplete"
        self.assertIn("world_infrastructure_or_incomplete", runner.validate_result(result, manifest)[0])

    def test_mock_execution_returns_verified_paths_and_preserves_invalid(self):
        manifest = self.prepare()
        invoke, calls = self.docker_mock(manifest, invalid=True)
        with patch.object(runner.subprocess, "run", side_effect=invoke):
            summary = runner.execute_prepared(self.output, self.lock)
        self.assertEqual(summary["operator_status"], "completed")
        self.assertEqual(summary["status"], "unscored")
        self.assertIsNone(summary["primary_score"])
        self.assertTrue(summary["provenance_verified"])
        self.assertEqual(summary["scored"], 3)
        self.assertEqual(summary["automatic_retries"], 0)
        self.assertTrue(Path(summary["result_path"]).is_file())
        self.assertEqual(sum(c[:2] == ["docker", "run"] for c in calls), 1)
        self.assertEqual(sum(c[:3] == ["docker", "rm", "--force"] for c in calls), 1)
        with self.assertRaises(FileExistsError):
            runner.execute_prepared(self.output, self.lock)

    def test_timeout_is_unscored_cleanup_attempted_no_retry(self):
        manifest = self.prepare()
        invoke, calls = self.docker_mock(manifest, timeout=True)
        with patch.object(runner.subprocess, "run", side_effect=invoke):
            summary = runner.execute_prepared(self.output, self.lock)
        self.assertEqual(summary["operator_status"], "infrastructure_or_incomplete")
        self.assertIsNone(summary["primary_score"])
        self.assertIn("operator_failure", summary["diagnostics"])
        self.assertEqual(sum(c[:2] == ["docker", "run"] for c in calls), 1)
        self.assertEqual(sum(c[:3] == ["docker", "rm", "--force"] for c in calls), 1)
        self.assertEqual(runner.read_json(self.output / "operator.private.json")["error_type"], "TimeoutExpired")

    def test_malformed_result_returns_infrastructure_record_instead_of_crashing(self):
        manifest = self.prepare()
        invoke, calls = self.docker_mock(manifest)

        def malformed(command, **kwargs):
            response = invoke(command, **kwargs)
            if command[:2] == ["docker", "run"]:
                runner.dump(self.output / "output/result.json", ["not a result object"])
            return response

        with patch.object(runner.subprocess, "run", side_effect=malformed):
            summary = runner.execute_prepared(self.output, self.lock)
        self.assertEqual(summary["operator_status"], "infrastructure_or_incomplete")
        self.assertIsNone(summary["primary_score"])
        self.assertIn("result_missing_or_invalid", summary["diagnostics"])

    def test_changed_staging_cannot_execute(self):
        self.prepare()
        path = self.output / "stage/candidate/controller.py"
        path.chmod(0o644)
        self.put(path, "changed\n")
        with patch.object(runner.subprocess, "run", side_effect=AssertionError("must not call Docker")):
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                runner.execute_prepared(self.output, self.lock)


if __name__ == "__main__":
    unittest.main()

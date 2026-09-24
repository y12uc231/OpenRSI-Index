"""Research scoring, per-call accounting, and immutable source selection; no inference."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('research_score_test', ROOT / 'research/evaluate.py')
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)
PROFILE = json.loads((ROOT / 'compute/qwen38.json').read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def metadata():
    return {'status': 'completed', 'usage_complete': True,
            'generation_requests_started': 1, 'automatic_retries': 0,
            'all_generated_token_ids_counted': True,
            'model_requested': PROFILE['model_id'], 'model_revision_expected': PROFILE['model_revision'],
            'vllm_version': PROFILE['vllm_version'],
            'usage': [{'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15,
                       'cached_input_tokens': 4, 'reasoning_output_tokens': 3}]}


def calls(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name in scoring.CALLS:
        write(directory / name / 'metadata.json', metadata())
    return scoring.audit_usage(directory, PROFILE)


def report(passed, accounting=None):
    if accounting is None:
        accounting = {'bounded_usage_verified': True, 'known_input_plus_output': 90,
                      'total_input_plus_output': 90}
    return {'status': 'scored', 'generation_completed': True, 'infrastructure_affected': False,
            'calls': 6, 'accounting': accounting,
            'usage': {'calls_with_usage': 6, 'calls_marked_incomplete_usage': 0,
                      'total_input_plus_output': 90},
            'heldout': {'status': 'scored', 'total': 3, 'passed': passed,
                        'cases': [{'name': 'case-' + str(i), 'status': 'scored', 'passed': i < passed}
                                  for i in range(3)]}}


def source_fixture(base):
    root = base / 'source/contributor-work/livemigrate'
    for name in ('runtime.py', 'scenarios.py', 'API_CONTRACT.md', 'pilot/run.py',
                 'pilot/compatible_adapter.py', 'families/identity/runtime.py'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# trusted fixture\n')
    (root / 'pilot/scaffold.py').write_bytes((ROOT / 'pilot/scaffold.py').read_bytes())
    write(root / 'compute/qwen38.json', PROFILE)
    write(root / 'research/baseline.json', json.loads((ROOT / 'research/baseline.json').read_text()))
    relay = root.parent / 'relayrepair/pilot/codex_runner.py'
    relay.parent.mkdir(parents=True)
    relay.write_text('# required source dependency\n')
    return root


class ResearchScoreTests(unittest.TestCase):
    def test_macro_family_metric_and_full_consumption(self):
        result = scoring.aggregate({'amounts': report(3), 'identity': report(0)})
        self.assertEqual(result['score'], .5)
        self.assertEqual(result['family_scores'], {'amounts': 1., 'identity': 0.})
        self.assertTrue(result['bounded_usage_verified'])
        self.assertEqual(result['accounted_consumption']['total_input_plus_output'], 180)

    def test_first_invalid_family_does_not_drop_second_diagnostics_or_usage(self):
        bad = report(3)
        bad.update(status='candidate_invalid')
        result = scoring.aggregate({'amounts': bad, 'identity': report(2)})
        self.assertIsNone(result['score'])
        self.assertEqual(set(result['families']), {'amounts', 'identity'})
        self.assertEqual(result['families']['identity']['passed'], 2)
        self.assertEqual(result['accounted_consumption']['known_input_plus_output'], 180)
        missing = scoring.aggregate({'amounts': report(3)})
        self.assertIsNone(missing['score'])
        self.assertEqual(missing['families']['identity']['status'], 'not_run')
        self.assertFalse(missing['bounded_usage_verified'])

    def test_invalid_checks_case_shapes_and_unknown_usage_remain_unscored(self):
        for mutate in (
            lambda x: x.update(infrastructure_affected=True),
            lambda x: x.update(process_exit_code=1),
            lambda x: x['heldout']['cases'].pop(),
            lambda x: x['heldout']['cases'][0].update(passed=1),
            lambda x: x['heldout']['cases'][0].update(name='case-1'),
            lambda x: x.update(accounting={}),
        ):
            bad = copy.deepcopy(report(3))
            mutate(bad)
            self.assertIsNone(scoring.aggregate({'amounts': report(3), 'identity': bad})['score'])

    def test_six_partial_entries_cannot_masquerade_as_six_complete_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls(root)
            first, second = metadata(), metadata()
            first['usage'] = [{'input_tokens': 10}]
            second['usage'] = [{'output_tokens': 5}]
            write(root / 'call-00/metadata.json', first)
            write(root / 'call-01/metadata.json', second)
            audited = scoring.audit_usage(root, PROFILE)
            self.assertFalse(audited['bounded_usage_verified'])
            self.assertIsNone(audited['total_input_plus_output'])
            self.assertEqual(audited['known_input_plus_output'], 60)
            self.assertEqual(audited['reported_totals']['input_tokens'], 50)
            self.assertIsNone(scoring.aggregate({'amounts': report(3, audited), 'identity': report(3)})['score'])

    def test_identity_caps_retries_and_usage_attestations_are_per_call(self):
        mutations = (
            lambda x: x.pop('usage_complete'),
            lambda x: x.update(usage_complete=False),
            lambda x: x.update(generation_requests_started=2),
            lambda x: x.update(generation_requests_started=True),
            lambda x: x.update(automatic_retries=1),
            lambda x: x.update(model_revision_expected='a' * 40),
            lambda x: x.update(model_requested='another-model'),
            lambda x: x.update(vllm_version='another-version'),
            lambda x: x.update(all_generated_token_ids_counted=False),
            lambda x: x['usage'][0].update(input_tokens=-1, total_tokens=4),
            lambda x: x['usage'][0].update(input_tokens=True, total_tokens=6),
            lambda x: x['usage'][0].update(input_tokens=16385, total_tokens=16390),
            lambda x: x['usage'][0].update(output_tokens=16385, total_tokens=16395),
            lambda x: x['usage'][0].update(total_tokens=99),
            lambda x: x['usage'][0].update(cached_input_tokens=11),
            lambda x: x['usage'][0].update(reasoning_output_tokens=6),
            lambda x: x['usage'].append(dict(x['usage'][0])),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls(root)
            for mutate in mutations:
                changed = metadata()
                mutate(changed)
                write(root / 'call-02/metadata.json', changed)
                with self.subTest(metadata=changed):
                    self.assertFalse(scoring.audit_usage(root, PROFILE)['bounded_usage_verified'])
            write(root / 'call-02/metadata.json', metadata())
            result = scoring.audit_usage(root, PROFILE)
            self.assertTrue(result['bounded_usage_verified'])
            self.assertEqual(result['total_input_plus_output'], 90)
            self.assertEqual(result['reported_totals']['cached_input_tokens'], 24)
            self.assertEqual(result['reported_totals']['reasoning_output_tokens'], 18)

    def test_missing_extra_or_renamed_call_preserves_known_consumption_but_not_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls(root)
            write(root / 'call-06/metadata.json', metadata())
            result = scoring.audit_usage(root, PROFILE)
            self.assertFalse(result['bounded_usage_verified'])
            self.assertEqual(result['known_input_plus_output'], 105)
            (root / 'call-06/metadata.json').unlink()
            (root / 'call-06').rmdir()
            (root / 'call-05').rename(root / 'call-5')
            self.assertFalse(scoring.audit_usage(root, PROFILE)['bounded_usage_verified'])
            (root / 'call-5/metadata.json').unlink()
            result = scoring.audit_usage(root, PROFILE)
            self.assertFalse(result['bounded_usage_verified'])
            self.assertEqual(result['known_input_plus_output'], 75)


class SourceSnapshotTests(unittest.TestCase):
    def test_only_explicit_source_areas_and_extensions_are_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = source_fixture(base)
            for name in ('results/run/private.json', '__pycache__/cache.py', 'compute/weights/config.json',
                         'weights/model.json', 'pilot/nested/unselected.py', 'compute/model.safetensors'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('DO_NOT_COPY')
            frozen, manifest = scoring.freeze_sources(root, base / 'out/frozen')
            self.assertEqual(scoring.source_manifest(frozen), manifest)
            self.assertTrue((frozen.parent / 'relayrepair/pilot/codex_runner.py').is_file())
            self.assertNotIn('DO_NOT_COPY', '\n'.join(path.read_text() for path in (base / 'out/frozen').rglob('*') if path.is_file()))
            (frozen / 'runtime.py').write_text('# changed after copying\n')
            with self.assertRaises(scoring.SnapshotError):
                scoring.verify_snapshot(frozen, manifest)

    def test_source_change_during_copy_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = source_fixture(base)
            original = scoring.source_manifest
            reads = 0
            def manifest(path):
                nonlocal reads
                if path == root:
                    reads += 1
                    if reads == 2:
                        (root / 'runtime.py').write_text('# changed during copy\n')
                return original(path)
            with mock.patch.object(scoring, 'source_manifest', side_effect=manifest):
                with self.assertRaisesRegex(scoring.SnapshotError, 'during copy'):
                    scoring.freeze_sources(root, base / 'out/frozen')

    def exercise_main(self, base, mutate_frozen_after=None):
        base = base.resolve()
        root = source_fixture(base)
        out = base / 'run'
        commands = []
        def run(command, **unused):
            commands.append(command)
            pilot = Path(command[1])
            destination = Path(command[command.index('--output') + 1])
            profile = Path(command[-1])
            self.assertTrue(out / 'frozen' in pilot.parents)
            self.assertEqual(profile, pilot.parents[1] / 'compute/qwen38.json')
            self.assertEqual(json.loads(profile.read_text()), PROFILE)
            self.assertTrue(out / 'frozen' in Path(command[command.index('--task-root') + 1]).parents)
            calls(destination)
            write(destination / 'summary.json', report(3))
            if len(commands) == 1:
                # Original edits cannot affect the frozen profile used for family two.
                write(root / 'compute/qwen38.json', {**PROFILE, 'seed': 99})
            if len(commands) == mutate_frozen_after:
                (pilot.parents[1] / 'runtime.py').write_text('# changed frozen runtime\n')
            return types.SimpleNamespace(returncode=0)
        with mock.patch.object(scoring, 'ROOT', root), \
             mock.patch.object(scoring.subprocess, 'run', side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            scoring.main(['--scaffold', str(root / 'research/baseline.json'), '--output', str(out)])
        return json.loads((out / 'result.json').read_text()), commands

    def test_main_uses_frozen_paths_and_profile_for_both_families(self):
        with tempfile.TemporaryDirectory() as directory:
            result, commands = self.exercise_main(Path(directory))
            self.assertEqual(len(commands), 2)
            self.assertTrue(result['source_snapshot_verified'])
            self.assertTrue(result['bounded_usage_verified'])
            self.assertEqual(result['score'], 1.)
            self.assertEqual(result['accounted_consumption']['total_input_plus_output'], 180)

    def test_snapshot_changes_stop_future_execution_or_invalidate_completed_run_without_losing_usage(self):
        for after in (1, 2):
            with self.subTest(after=after), tempfile.TemporaryDirectory() as directory:
                result, commands = self.exercise_main(Path(directory), after)
                self.assertEqual(len(commands), after)
                self.assertFalse(result['source_snapshot_verified'])
                self.assertEqual(result['status'], 'unscored')
                self.assertIsNone(result['score'])
                self.assertEqual(set(result['families']), {'amounts', 'identity'})
                self.assertEqual(result['accounted_consumption']['known_input_plus_output'], after * 90)
                self.assertEqual(result['bounded_usage_verified'], after == 2)
                if after == 1:
                    self.assertEqual(result['families']['identity']['status'], 'not_run')


if __name__ == '__main__':
    unittest.main()

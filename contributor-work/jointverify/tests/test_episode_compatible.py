"""Offline backend/controller accounting tests; no Docker or inference endpoint."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from runner import episode
from runner.compatible import InferenceError, TokenLimitExceeded


class CompatibleEpisodeTests(unittest.TestCase):
    def test_backend_defaults_and_explicit_caps(self):
        common = ['--source', '/synthetic', '--task', 'fixture', '--output', '/synthetic-output']
        codex = episode.parse_args(common)
        self.assertEqual((codex.max_calls, codex.max_tool_seconds, codex.max_checks, codex.max_episode_seconds, codex.max_total_tokens),
                         (32, 900, 4, 3600, None))
        compatible = episode.parse_args(common + ['--backend', 'compatible'])
        self.assertEqual((compatible.max_calls, compatible.max_tool_seconds, compatible.max_checks, compatible.max_episode_seconds, compatible.max_total_tokens),
                         (200, 1800, 4, 3600, 1000000))
        explicit = episode.parse_args(common + ['--backend', 'compatible', '--max-calls', '7', '--max-total-tokens', '9000'])
        self.assertEqual((explicit.max_calls, explicit.max_total_tokens), (7, 9000))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            episode.parse_args(common + ['--max-total-tokens', '9000'])

    def run_episode(self, behavior='success', *, mock=False, total_tokens=1000000):
        with tempfile.TemporaryDirectory(prefix='jointverify-compatible-controller-') as temporary:
            base = Path(temporary)
            root = base / 'checkout/contributor-work/jointverify'
            (root / 'manifests').mkdir(parents=True)
            (root / 'policies/configs').mkdir(parents=True)
            (root / 'runner').mkdir()
            (root / 'runner/compatible.py').write_text('# Non-executable fixture adapter identity\n')
            source = base / 'source'
            source.mkdir()
            specs = {}
            for feature in [1, 2]:
                path = source / f'feature{feature}.md'
                path.write_text('Synthetic feature ' + str(feature))
                specs[str(feature)] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            case = {'task_id': 'fixture', 'features': [1, 2], 'feature_specs': specs,
                    'image': 'NOT_AN_IMAGE', 'base_commit': 'fixture-base', 'source_prefixes': ['package/']}
            (root / 'manifests/pilot-v1.json').write_text(json.dumps({'cases': [case]}))
            (root / 'policies/configs/periodic.json').write_text(json.dumps({'mode': 'periodic', 'interval': 2}))
            output = base / 'output'
            inference_calls, judge_calls, containers = [], [], []
            def container(*_):
                gateway = Mock(original_base='fixture-base')
                gateway.patch.return_value = ''
                containers.append(gateway)
                return gateway
            def evaluate(task, patches, mode, **kwargs):
                judge_calls.append(mode)
                return {'validinfra': True, 'both_features_passed': False}
            def infer(prompt, folder, schema, *, timeout, remaining_tokens, on_preflight):
                inference_calls.append(remaining_tokens)
                folder.mkdir()
                if behavior == 'context_limit':
                    (folder / 'metadata.json').write_text(json.dumps({'generation_requests_started': 0, 'usage': []}))
                    raise TokenLimitExceeded('Declared context cap cannot fit the next request')
                on_preflight({'input_upper_bound': 10, 'output_token_limit': 4096})
                # The shared reservation must already be persisted before generation.
                reserved = json.loads((output / 'budget.json').read_text())
                self.assertEqual(reserved['calls'][-1]['reserved_tokens'], 4106)
                self.assertEqual(reserved['calls'][-1]['status'], 'reserved')
                usage = [{'input_tokens': 10, 'output_tokens': 4}]
                metadata = {'usage': usage, 'usage_complete': True, 'generation_requests_started': 1}
                if behavior == 'missing_usage':
                    metadata.update(usage=[], usage_complete=False)
                (folder / 'metadata.json').write_text(json.dumps(metadata))
                if behavior == 'missing_usage':raise TimeoutError('Generation timed out after reservation')
                if behavior == 'invalid_output':raise InferenceError('Truncated completion with usage')
                return {'action': 'finish', 'command': '', 'message': '', 'summary': 'Offline fixture'}
            argv = ['episode.py', '--source', str(source), '--task', 'fixture', '--output', str(output),
                    '--backend', 'compatible', '--max-total-tokens', str(total_tokens)]
            if mock:argv.append('--mock')
            with patch.object(episode, 'ROOT', root), patch.object(episode, 'PrivateContainer', side_effect=container), \
                    patch.object(episode, 'compatible_infer', side_effect=infer), \
                    patch.object(episode, 'codex_infer', side_effect=AssertionError('Wrong backend called')), \
                    patch('evaluator.checker.evaluate', side_effect=evaluate), \
                    patch.object(episode.sys, 'argv', argv), redirect_stdout(io.StringIO()):
                episode.main()
            for gateway in containers:gateway.close.assert_called_once()
            return (json.loads((output / 'status.json').read_text()),
                    json.loads((output / 'budget.json').read_text()),
                    json.loads((output / 'run_config.json').read_text()), inference_calls, judge_calls)

    def test_success_has_exact_shared_reservations_and_final_judge(self):
        status, budget, config, calls, judges = self.run_episode()
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(budget['calls_started'], 2)
        self.assertEqual(budget['total_tokens'], 28)
        self.assertEqual(calls, [1000000, 999986])
        self.assertEqual(judges, ['judge'])
        self.assertEqual(config['budget_lane'], 'shared_bounded_token_reservations_and_tool_wall_time')

    def test_output_failure_still_settles_consumed_usage_without_retry(self):
        status, budget, _, calls, judges = self.run_episode('invalid_output')
        self.assertEqual(status['status'], 'incomplete')
        self.assertEqual(budget['calls_started'], 1)
        self.assertEqual(budget['total_tokens'], 14)
        self.assertTrue(budget['token_telemetry_valid'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(judges, ['judge'])

    def test_started_generation_missing_usage_is_unscored_and_not_retried(self):
        status, budget, _, calls, judges = self.run_episode('missing_usage')
        self.assertEqual(status['status'], 'unscored_budget_or_telemetry_failure')
        self.assertEqual(budget['calls_started'], 1)
        self.assertIsNone(budget['total_tokens'])
        self.assertFalse(budget['token_telemetry_valid'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(judges, ['judge'])

    def test_no_generation_context_cap_exhaustion_still_scores_current_patches(self):
        status, budget, _, calls, judges = self.run_episode('context_limit')
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['work_stop'], 'budget_exhausted')
        self.assertEqual(budget['calls_started'], 0)
        self.assertEqual(budget['total_tokens'], 0)
        self.assertEqual(judges, ['judge'])

    def test_no_generation_shared_cap_exhaustion_still_judges(self):
        status, budget, _, calls, judges = self.run_episode(total_tokens=100)
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['work_stop'], 'budget_exhausted')
        self.assertEqual(budget['calls_started'], 0)
        self.assertEqual(judges, ['judge'])

    def test_compatible_mock_is_bounded_and_never_calls_model(self):
        status, budget, config, calls, judges = self.run_episode(mock=True)
        self.assertEqual(calls, [])
        self.assertEqual(status['measurement_type'], 'MOCK_NOT_MODEL')
        self.assertEqual(config['inference'], 'MOCK_NOT_MODEL')
        self.assertEqual(budget['token_budget_mode'], 'bounded_reservations')
        self.assertEqual(budget['total_tokens'], 4)
        self.assertEqual(judges, ['judge'])


if __name__ == '__main__':
    unittest.main()

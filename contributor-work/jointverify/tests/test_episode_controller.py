"""Controller deadline tests with fake containers, inference, and evaluator only."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runner import episode


class FakeContainer:
    instances = []

    def __init__(self, image, role):
        self.original_base = 'fixture-base'
        self.role = role
        self.commands = []
        self.closed = False
        self.__class__.instances.append(self)

    def write(self, path, value):
        pass

    def patch(self):
        return f'diff --git a/package/{self.role}.py b/package/{self.role}.py\n+fixture\n'

    def execute(self, command):
        self.commands.append(command)
        return {'wall_seconds': 0, 'stdout': '', 'stderr': '', 'exit_code': 0}

    def close(self):
        self.closed = True


class EpisodeControllerTests(unittest.TestCase):
    def fixture(self, temporary):
        base = Path(temporary)
        root = base / 'checkout' / 'contributor-work' / 'jointverify'
        (root / 'manifests').mkdir(parents=True)
        (root / 'policies' / 'configs').mkdir(parents=True)
        adapter = root.parent / 'relayrepair' / 'pilot' / 'codex_runner.py'
        adapter.parent.mkdir(parents=True)
        adapter.write_text('# OFFLINE FIXTURE, not executable model code\n')
        source = base / 'source'
        source.mkdir()
        specs = {}
        for feature in [1, 2]:
            path = source / f'feature{feature}.md'
            path.write_text(f'Synthetic feature {feature}')
            specs[str(feature)] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        case = {'task_id': 'offline_fixture', 'feature_specs': specs, 'features': [1, 2],
                'image': 'NOT_A_DOCKER_IMAGE', 'base_commit': 'fixture-base', 'source_prefixes': ['package/']}
        (root / 'manifests' / 'pilot-v1.json').write_text(json.dumps({'cases': [case]}))
        (root / 'policies' / 'configs' / 'periodic.json').write_text(json.dumps({'mode': 'periodic', 'interval': 2}))
        return root, source, base / 'output'

    def run_fixture(self, *, nested_stage=None, episode_seconds=3600, consume_episode_in_inference=False):
        with tempfile.TemporaryDirectory(prefix='jointverify-controller-test-') as temporary:
            root, source, output = self.fixture(temporary)
            calls = []
            clock = [0.0]
            FakeContainer.instances = []

            def evaluate(task, patches, mode, **kwargs):
                calls.append({'mode': mode, **kwargs})
                if mode == 'public':
                    return {'validinfra': False, nested_stage: {'validinfra': False, 'budget_exhausted': True}}
                return {'validinfra': True, 'both_features_passed': False, 'measurement_type': 'OFFLINE_FIXTURE_NOT_MODEL'}

            def infer(prompt, folder, schema, timeout):
                folder.mkdir()
                (folder / 'metadata.json').write_text(json.dumps({'usage': [{'input_tokens': 1, 'output_tokens': 1}]}))
                clock[0] = episode_seconds
                return {'action': 'shell', 'command': 'must never run', 'message': '', 'summary': 'fixture'}

            argv = ['episode.py', '--source', str(source), '--task', 'offline_fixture', '--output', str(output),
                    '--max-episode-seconds', str(episode_seconds)]
            if not consume_episode_in_inference:
                argv.append('--mock')
            with patch.object(episode, 'ROOT', root), patch.object(episode, 'PrivateContainer', FakeContainer), \
                    patch.object(episode, 'codex_infer', side_effect=infer), \
                    patch('evaluator.checker.evaluate', side_effect=evaluate), \
                    patch.object(episode.time, 'monotonic', side_effect=lambda: clock[0]), \
                    patch.object(episode.sys, 'argv', argv), redirect_stdout(io.StringIO()):
                episode.main()
            status = json.loads((output / 'status.json').read_text())
            self.assertTrue(all(c.closed for c in FakeContainer.instances))
            return status, calls, FakeContainer.instances

    def test_nested_merge_deadline_still_runs_final_judge(self):
        status, calls, _ = self.run_fixture(nested_stage='merge')
        self.assertEqual([c['mode'] for c in calls], ['public', 'judge'])
        self.assertEqual(status['status'], 'completed')
        self.assertTrue(status['tool_time_limit_reached'])
        self.assertEqual(status['work_stop'], 'budget_exhausted')

    def test_nested_test_deadline_uses_remaining_episode_and_still_judges(self):
        status, calls, _ = self.run_fixture(nested_stage='public_check', episode_seconds=100)
        self.assertEqual([c['mode'] for c in calls], ['public', 'judge'])
        self.assertEqual(calls[0]['max_seconds'], 95)
        self.assertTrue(status['episode_time_limit_reached'])
        self.assertEqual(status['status'], 'completed')

    def test_inference_consuming_episode_budget_cannot_launch_late_shell(self):
        status, calls, containers = self.run_fixture(episode_seconds=100, consume_episode_in_inference=True)
        self.assertEqual([c['mode'] for c in calls], ['judge'])
        self.assertTrue(status['episode_time_limit_reached'])
        self.assertEqual(status['status'], 'completed')
        self.assertTrue(all(c.commands == [] for c in containers))


if __name__ == '__main__':
    unittest.main()

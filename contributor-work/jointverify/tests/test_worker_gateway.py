"""Offline gateway/worker contract tests. No Docker or model calls."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runner.worker import PrivateContainer, Worker, shell


class FakeContainer:
    def __init__(self):
        self.commands = []
        self.patch_calls = 0
        self.diff = 'diff --git a/example.py b/example.py\n+updated\n'

    def execute(self, command):
        self.commands.append(command)
        return {'exit_code': 0, 'stdout': 'VISIBLE_TOOL_RESULT', 'stderr': '',
                'stdout_truncated': False, 'stderr_truncated': False, 'wall_seconds': 0.1}

    def patch(self):
        self.patch_calls += 1
        return self.diff


def response(action='shell', command='python -m pytest', message='Working on the parser.'):
    return {'action': action, 'command': command, 'message': message, 'summary': 'Progress'}


class ActionContractTests(unittest.TestCase):
    def setUp(self):
        self.container = FakeContainer()
        self.worker = Worker('worker_1', 'PRIVATE_FEATURE_BRIEF', self.container)

    def test_invalid_actions_have_no_gateway_or_history_side_effect(self):
        extra = response()
        extra['unexpected'] = 'field'
        missing = response()
        del missing['summary']
        wrong_type = response()
        wrong_type['command'] = ['not', 'a', 'string']
        invalid = [None, [], extra, missing, wrong_type,
                   response(action='browser'), response(command=' \n '),
                   response(action='finish', command='rm -f x'),
                   response(action='message', command='echo command')]
        for item in invalid:
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    self.worker.accept(item)
                self.assertEqual(self.container.commands, [])
                self.assertEqual(self.container.patch_calls, 0)
                self.assertEqual(self.worker.history, [])
                self.assertEqual(self.worker.turns, 0)

    def test_shell_action_records_observation_and_actual_patch_hash(self):
        action = response()
        observation = self.worker.accept(action)
        self.assertEqual(self.container.commands, ['python -m pytest'])
        self.assertEqual(observation['stdout'], 'VISIBLE_TOOL_RESULT')
        self.assertEqual([item['kind'] for item in self.worker.history], ['action', 'tool'])
        self.assertEqual(self.worker.latest_patch, self.container.diff)
        self.assertEqual(self.worker.revision, hashlib.sha256(self.container.diff.encode()).hexdigest())
        self.assertFalse(self.worker.done)

    def test_finish_and_message_never_execute_shell_and_can_reopen_work(self):
        self.worker.accept(response(action='finish', command=''))
        self.assertTrue(self.worker.done)
        self.worker.accept(response(action='message', command='', message='Repairing joint failure.'))
        self.assertFalse(self.worker.done)
        self.assertEqual(self.container.commands, [])
        self.assertEqual(self.container.patch_calls, 2)
        self.assertEqual(self.worker.turns, 2)


class ContextContractTests(unittest.TestCase):
    def test_old_tool_output_omitted_explicitly_while_messages_and_brief_survive(self):
        worker = Worker('worker_1', 'EXACT_PRIVATE_BRIEF', FakeContainer())
        worker.history = [
            {'kind': 'message', 'sender': 'worker_2', 'message': 'KEEP_OLD_PEER_MESSAGE'},
            {'kind': 'tool', 'stdout': 'OLD_OUTPUT_' + 'a' * 30000},
            {'kind': 'action', **response(action='message', command='', message='KEEP_OLD_ACTION')},
            {'kind': 'tool', 'stdout': 'MIDDLE_OUTPUT_' + 'b' * 30000},
            {'kind': 'tool', 'stdout': 'RECENT_OUTPUT_' + 'c' * 30000}]
        before = deepcopy(worker.history)
        prompt = worker.prompt('peer-revision-123', remaining=32)
        history = json.loads(prompt.split('EXPLICIT HISTORY:\n', 1)[1])
        self.assertIn('EXACT_PRIVATE_BRIEF', prompt)
        self.assertIn('peer-revision-123', prompt)
        self.assertIn('Team calls remaining: 32', prompt)
        self.assertIn('KEEP_OLD_PEER_MESSAGE', prompt)
        self.assertIn('KEEP_OLD_ACTION', prompt)
        self.assertNotIn('OLD_OUTPUT_', prompt)
        self.assertIn('MIDDLE_OUTPUT_', prompt)
        self.assertIn('RECENT_OUTPUT_', prompt)
        self.assertTrue(any('omitted by fixed 80k-character context policy' in item.get('observation', '')
                            for item in history))
        self.assertEqual(worker.history, before)

    def test_source_brief_is_never_truncated_by_tool_history_rule(self):
        brief = 'PRIVATE_FEATURE_' + 'x' * 90000
        worker = Worker('worker_1', brief, FakeContainer())
        worker.history = [{'kind': 'tool', 'stdout': 'recent public evidence'}]
        self.assertIn(brief, worker.prompt('', remaining=1))


class GatewayContractTests(unittest.TestCase):
    def test_commands_are_docker_argv_and_output_truncation_is_visible(self):
        container = object.__new__(PrivateContainer)
        container.name = 'offline-fixture-container'
        container.command_seconds = 7
        command = 'echo first; cd /tmp; printf second'
        completed = SimpleNamespace(returncode=124, stdout='a' * 25000, stderr='b' * 7000)
        with patch('runner.worker.shell', return_value=completed) as launch:
            result = container.execute(command)
        argv = launch.call_args.args[0]
        self.assertEqual(argv[:3], ['docker', 'exec', 'offline-fixture-container'])
        self.assertIn('timeout', argv)
        self.assertEqual(argv[-3:], ['bash', '-lc', 'cd /workspace/repo && ' + command])
        self.assertEqual(launch.call_args.kwargs['timeout'], 22)
        self.assertEqual(result['exit_code'], 124)
        self.assertEqual(len(result['stdout']), 24000)
        self.assertEqual(len(result['stderr']), 6000)
        self.assertTrue(result['stdout_truncated'])
        self.assertTrue(result['stderr_truncated'])

    def test_controller_subprocess_helper_does_not_enable_host_shell(self):
        completed = SimpleNamespace(returncode=0, stdout='ok', stderr='')
        argv = ['docker', 'exec', 'fixture', 'bash', '-lc', 'echo inside; echo container']
        with patch('runner.worker.subprocess.run', return_value=completed) as launch:
            self.assertIs(shell(argv, data='synthetic', timeout=3), completed)
        self.assertEqual(launch.call_args.args, (argv,))
        self.assertFalse(launch.call_args.kwargs.get('shell', False))
        self.assertEqual(launch.call_args.kwargs['input'], 'synthetic')


if __name__ == '__main__':
    unittest.main()

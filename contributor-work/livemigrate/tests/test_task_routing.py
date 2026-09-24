"""Task routing without model calls; oracle data must stay outside Docker."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))
import isolated

spec = importlib.util.spec_from_file_location('livemigrate_pilot_routing_test', CORE / 'pilot' / 'run.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


def family(root, name):
    root.mkdir()
    (root / 'starter').mkdir()
    (root / 'reference').mkdir()
    (root / 'API_CONTRACT.md').write_text('PUBLIC CONTRACT ' + name)
    (root / 'reference' / 'immutable_v1.py').write_text('# PUBLIC LEGACY ' + name)
    for role in ('db', 'api', 'consumer'):
        (root / 'starter' / (role + '.py')).write_text('# PUBLIC STARTER ' + name + ' ' + role)
        (root / 'reference' / (role + '.py')).write_text('# SECRET SOLUTION ' + name)
    (root / 'scenarios.py').write_text('MARKER = ' + repr(name) + '\nSECRET = "HIDDEN SCHEDULE"\n')
    (root / 'runtime.py').write_text('''
from pathlib import Path
import sqlite3
import tempfile
import scenarios
HERE = Path(__file__).resolve().parent
SECRET = 'HIDDEN ORACLE'
def run_suite(candidate, suite, invoke):
    with tempfile.TemporaryDirectory() as directory:
        conn = sqlite3.connect(str(Path(directory) / 'state.sqlite'))
        conn.execute('CREATE TABLE state(value TEXT)')
        conn.commit()
        try:
            result = invoke('db', 'backfill', conn, 'customer:alpha', 3)
        finally:
            conn.close()
    return {'family': scenarios.MARKER, 'runtime_root': str(HERE), 'rpc': result}
''')
    return root.resolve()


class TaskRoutingTests(unittest.TestCase):
    def test_local_model_default_and_sol_record_requested_alias_and_provenance(self):
        for requested, expected, source in ((None, 'gpt-6-astra', 'local_cli_default'),
                                            ('gpt-6-sol', 'gpt-6-sol', 'local_model_argument')):
            with self.subTest(requested=requested), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                task = family(root / 'task', 'CUSTOM')
                seen = []
                backend = types.SimpleNamespace(MODEL='unused', EFFORT='unused')
                def infer(prompt, call_dir, output_schema, timeout):
                    seen.append((backend.MODEL, backend.EFFORT))
                    call_dir.mkdir()
                    (call_dir / 'metadata.json').write_text(json.dumps({'model_requested': backend.MODEL,
                        'reasoning_effort': backend.EFFORT, 'status': 'completed', 'usage': []}))
                    return {key: '# generated ' + key for key in output_schema['required']}
                backend.infer = infer
                arguments = ['--task-root', str(task), '--mode', 'centralized', '--output', str(root / 'output')]
                if requested:
                    arguments += ['--local-model', requested]
                with mock.patch.object(pilot, 'load_backend', return_value=backend), \
                     mock.patch.object(pilot, 'source_hashes', return_value={'fixture': 'hash'}), \
                     mock.patch.object(pilot, 'check', return_value={'status': 'scored', 'score': 1.0}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    pilot.main(arguments)
                self.assertEqual(seen, [(expected, 'ultra')] * 6)
                summary = json.loads((root / 'output' / 'summary.json').read_text())
                self.assertEqual(summary['requested_model'], expected)
                self.assertEqual(summary['reasoning_effort'], 'ultra')
                self.assertEqual(summary['model_selection_source'], source)
                self.assertEqual(summary['check_timeout_seconds'], 180)
                for path in (root / 'output').glob('call-*/metadata.json'):
                    self.assertEqual(json.loads(path.read_text())['model_selection_source'], source)

    def test_local_model_and_adapter_are_rejected_before_any_work(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'must-not-exist'
            with mock.patch.object(pilot, 'load_backend') as backend, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                pilot.main(['--mode', 'team', '--output', str(output), '--local-model', 'gpt-6-sol',
                            '--adapter-command', 'adapter'])
            self.assertEqual(stopped.exception.code, 2)
            backend.assert_not_called()
            self.assertFalse(output.exists())

    def test_cli_alias_failure_is_infrastructure_and_never_a_model_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = family(root / 'task', 'CUSTOM')
            backend = types.SimpleNamespace(MODEL='unused', EFFORT='unused')
            def infer(prompt, call_dir, output_schema, timeout):
                call_dir.mkdir()
                (call_dir / 'metadata.json').write_text(json.dumps({'status': 'invalid', 'return_code': 1, 'usage': []}))
                raise RuntimeError('CLI rejected requested alias')
            backend.infer = infer
            with mock.patch.object(pilot, 'load_backend', return_value=backend), \
                 mock.patch.object(pilot, 'source_hashes', return_value={'fixture': 'hash'}), \
                 self.assertRaises(pilot.LocalInferenceInfrastructureError):
                pilot.main(['--task-root', str(task), '--mode', 'centralized', '--output', str(root / 'output'),
                            '--local-model', 'gpt-6-sol', '--check-timeout', '900'])
            failure = json.loads((root / 'output' / 'failure.json').read_text())
            self.assertEqual(failure['status'], 'incomplete')
            self.assertEqual(failure['failure_category'], 'infrastructure')
            self.assertTrue(failure['infrastructure_affected'])
            self.assertEqual(failure['requested_model'], 'gpt-6-sol')
            self.assertEqual(failure['check_timeout_seconds'], 900)
            self.assertNotIn('score', failure)
            metadata = json.loads((root / 'output' / 'call-00' / 'metadata.json').read_text())
            self.assertEqual(metadata['model_requested'], 'gpt-6-sol')
            self.assertEqual(metadata['model_selection_source'], 'local_model_argument')

    def test_adapter_envelope_records_usage_but_legacy_does_not_invent_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            response = {'db': '# source', 'message': 'note'}
            legacy = root / 'call-00'
            legacy.mkdir()
            self.assertEqual(pilot.record_adapter_response(response, legacy), response)
            self.assertFalse((legacy / 'metadata.json').exists())
            current = root / 'call-01'
            current.mkdir()
            metadata = {'usage': [{'input_tokens': 100, 'output_tokens': 25, 'cached_input_tokens': 40}]}
            self.assertEqual(pilot.record_adapter_response({'response': response, 'metadata': metadata}, current), response)
            self.assertEqual(json.loads((current / 'response.json').read_text()), response)
            self.assertEqual(json.loads((current / 'metadata.json').read_text()), metadata)
            self.assertEqual(pilot.usage_summary(root)['total_input_plus_output'], 125)
            self.assertEqual(pilot.usage_summary(root)['calls_with_usage'], 1)
            for invalid in ({'response': response}, {'metadata': metadata},
                            {'response': response, 'metadata': metadata, 'extra': 1},
                            {'response': response, 'metadata': []}, ['not an object']):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    pilot.record_adapter_response(invalid, root)

    def test_check_launches_core_wrapper_with_selected_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = family(root / 'task', 'CUSTOM')
            completed = types.SimpleNamespace(returncode=0, stdout='{"status":"scored","score":1.0}', stderr='')
            with mock.patch.object(pilot.subprocess, 'run', return_value=completed) as run:
                self.assertEqual(pilot.check(root / 'candidate', 'public', root / 'result.json', task)['score'], 1.0)
                self.assertEqual(run.call_args.kwargs['timeout'], 180)
                pilot.check(root / 'candidate', 'heldout', root / 'result.json', task, timeout=900)
                self.assertEqual(run.call_args.kwargs['timeout'], 900)
            command = run.call_args.args[0]
            self.assertEqual(command[1], str(CORE / 'isolated.py'))
            self.assertEqual(command[command.index('--task-root') + 1], str(task))

    def test_scoped_runtime_uses_selected_scenarios_and_restores_import_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            first = family(Path(directory) / 'first', 'FIRST')
            second = family(Path(directory) / 'second', 'SECOND')
            previous = types.ModuleType('scenarios')
            previous.MARKER = 'UNRELATED'
            before = {name for name in sys.modules if name.startswith('livemigrate_task_')}
            with mock.patch.dict(sys.modules, {'scenarios': previous}):
                for root, marker in ((first, 'FIRST'), (second, 'SECOND')):
                    with isolated.task_runtime(root) as runtime:
                        self.assertEqual(runtime.scenarios.MARKER, marker)
                        self.assertEqual(runtime.HERE, root)
                    self.assertIs(sys.modules['scenarios'], previous)
            self.assertEqual({name for name in sys.modules if name.startswith('livemigrate_task_')}, before)

    def test_isolated_cli_routes_host_oracle_but_never_mounts_task_root(self):
        with tempfile.TemporaryDirectory() as directory:
            task = family(Path(directory) / 'hidden-task', 'SELECTED')
            candidate = Path(directory) / 'candidate'
            candidate.mkdir()
            for role in ('db', 'api', 'consumer'):
                (candidate / (role + '.py')).write_text('raise RuntimeError("must not import in host")\n')
            commands = []
            requests = []

            def command_runner(command, **kwargs):
                commands.append(command)
                if command[1] == 'exec':
                    requests.append(json.loads(kwargs['payload']))
                    return 0, b'{"rpc_version":1,"ok":true,"result":{"cursor":"customer:omega","done":true}}', b''
                return 0, b'container-id\n', b''

            invoker_class = isolated.DockerInvoker
            def invoker(*args):
                return invoker_class(*args, command_runner=command_runner)

            output = io.StringIO()
            with mock.patch.object(isolated, 'DockerInvoker', side_effect=invoker), contextlib.redirect_stdout(output):
                isolated.main(['--candidate', str(candidate), '--task-root', str(task), '--suite', 'heldout'])
            result = json.loads(output.getvalue())
            self.assertEqual(result['family'], 'SELECTED')
            self.assertEqual(result['runtime_root'], str(task))
            self.assertEqual(result['rpc'], {'cursor': 'customer:omega', 'done': True})
            self.assertEqual(requests[0]['args'], ['customer:alpha', 3])
            self.assertEqual(set(requests[0]), {'role', 'function', 'database', 'args'})
            start = next(command for command in commands if command[1] == 'run')
            mounts = [start[i + 1] for i, part in enumerate(start) if part in ('--mount', '--volume')]
            self.assertEqual(len(mounts), 3)
            self.assertTrue(any(str(CORE / 'candidate_driver.py') in mount for mount in mounts))
            self.assertFalse(any(str(task) in mount or str(candidate) in mount for mount in mounts))
            self.assertNotIn('HIDDEN', json.dumps(requests))

    def test_optional_history_is_exact_scoped_and_restored_for_distinct_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            first = family(Path(directory) / 'first', 'FIRST')
            second = family(Path(directory) / 'second', 'SECOND')
            for root, marker in ((first, 'FIRST HISTORY'), (second, 'SECOND HISTORY')):
                (root / 'history.py').write_text('MARKER = ' + repr(marker) + '\n')
                with (root / 'runtime.py').open('a') as stream:
                    stream.write('\nimport history\n')
                with (root / 'scenarios.py').open('a') as stream:
                    stream.write('\nimport history\n')
            previous = types.ModuleType('history')
            previous.MARKER = 'UNRELATED'
            before_path = list(sys.path)
            before_modules = {name for name in sys.modules if name.startswith('livemigrate_task_')}
            with mock.patch.dict(sys.modules, {'history': previous}):
                with isolated.task_runtime(first) as first_runtime:
                    self.assertEqual(first_runtime.history.MARKER, 'FIRST HISTORY')
                    self.assertIs(first_runtime.scenarios.history, first_runtime.history)
                    with isolated.task_runtime(second) as second_runtime:
                        self.assertEqual(second_runtime.history.MARKER, 'SECOND HISTORY')
                        self.assertIs(second_runtime.scenarios.history, second_runtime.history)
                        self.assertIsNot(second_runtime.history, first_runtime.history)
                    self.assertIs(sys.modules['history'], first_runtime.history)
                self.assertIs(sys.modules['history'], previous)
                (second / 'runtime.py').write_text('import history\nraise RuntimeError("load failure")\n')
                with self.assertRaisesRegex(RuntimeError, 'load failure'):
                    with isolated.task_runtime(second):
                        self.fail('broken runtime must not yield')
                self.assertIs(sys.modules['history'], previous)
            self.assertEqual(sys.path, before_path)
            self.assertEqual({name for name in sys.modules if name.startswith('livemigrate_task_')}, before_modules)

    def test_public_packet_excludes_solutions_schedules_and_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            task = family(Path(directory) / 'task', 'CUSTOM')
            (task / 'PUBLIC_SCENARIO.json').write_text('{"name":"PUBLIC_EXAMPLE"}')
            (task / 'heldout.json').write_text('{"name":"SECRET_EXTRA_SCHEDULE"}')
            (task / 'history.py').write_text('SECRET = "HIDDEN HISTORY ORACLE"\n')
            packet, code = pilot.public_packet(task)
            visible = packet + json.dumps(code)
            self.assertIn('PUBLIC CONTRACT CUSTOM', visible)
            self.assertIn('PUBLIC LEGACY CUSTOM', visible)
            self.assertIn('PUBLIC STARTER CUSTOM', visible)
            self.assertIn('PUBLIC_EXAMPLE', visible)
            self.assertNotIn('HIDDEN', visible)
            self.assertNotIn('SECRET SOLUTION', visible)
            self.assertNotIn('SECRET_EXTRA_SCHEDULE', visible)
            (task / 'scenarios.py').unlink()
            with self.assertRaisesRegex(RuntimeError, 'scenarios.py'):
                pilot.public_packet(task)

    def test_hashes_cover_task_sources_core_driver_pilot_and_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = root / 'livemigrate'
            (core / 'pilot').mkdir(parents=True)
            for name in ('isolated.py', 'candidate_driver.py', 'pilot/run.py'):
                (core / name).write_text('# CORE ' + name)
            transport = root / 'relayrepair' / 'pilot' / 'codex_runner.py'
            transport.parent.mkdir(parents=True)
            transport.write_text('# TRANSPORT')
            task = family(root / 'task', 'CUSTOM')
            with mock.patch.object(pilot, 'CORE_ROOT', core):
                hashes = pilot.source_hashes(task)
                for key in ('isolated.py', 'candidate_driver.py', 'pilot/run.py',
                            '../relayrepair/pilot/codex_runner.py', 'task/API_CONTRACT.md',
                            'task/runtime.py', 'task/scenarios.py', 'task/reference/immutable_v1.py',
                            'task/starter/api.py', 'task/reference/consumer.py'):
                    self.assertIn(key, hashes)
                self.assertEqual(hashes['task/runtime.py'], hashlib.sha256((task / 'runtime.py').read_bytes()).hexdigest())
                (task / 'runtime.py').write_text('# CHANGED ORACLE')
                self.assertNotEqual(pilot.source_hashes(task)['task/runtime.py'], hashes['task/runtime.py'])

    def test_pilot_routes_all_checks_to_selected_family_without_model_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = family(root / 'task', 'CUSTOM')
            prompts, checks, timeouts = [], [], []

            def infer(prompt, call_dir, output_schema, timeout):
                prompts.append(prompt)
                timeouts.append(timeout)
                return {key: '# generated ' + key for key in output_schema['required']}

            def check(candidate, suite, destination, task_root, timeout=180):
                checks.append((suite, task_root, timeout))
                return {'status': 'scored', 'score': 1.0}

            backend = types.SimpleNamespace(infer=infer, MODEL='mock', EFFORT='none')
            with mock.patch.object(pilot, 'load_backend', return_value=backend), \
                 mock.patch.object(pilot, 'source_hashes', return_value={'fixture': 'hash'}), \
                 mock.patch.object(pilot, 'check', side_effect=check), contextlib.redirect_stdout(io.StringIO()):
                pilot.main(['--task-root', str(task), '--mode', 'centralized', '--output', str(root / 'output'),
                            '--inference-timeout', '1800', '--check-timeout', '900'])
            self.assertEqual(checks, [('public', task, 900), ('public', task, 900), ('heldout', task, 900)])
            self.assertEqual(len(prompts), 6)
            self.assertEqual(timeouts, [1800] * 6)
            self.assertTrue(all('PUBLIC CONTRACT CUSTOM' in prompt for prompt in prompts))
            self.assertTrue(all('HIDDEN' not in prompt and 'SECRET SOLUTION' not in prompt for prompt in prompts))
            summary = json.loads((root / 'output' / 'summary.json').read_text())
            self.assertEqual(summary['task_root'], str(task))
            self.assertEqual(summary['inference_timeout_seconds'], 1800)
            self.assertEqual(summary['check_timeout_seconds'], 900)
            self.assertFalse(summary['infrastructure_affected'])

    def test_nonpositive_check_timeout_is_rejected_before_any_work(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'must-not-exist'
            with mock.patch.object(pilot, 'load_backend') as backend, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                pilot.main(['--mode', 'team', '--output', str(output), '--check-timeout', '0'])
            self.assertEqual(stopped.exception.code, 2)
            backend.assert_not_called()
            self.assertFalse(output.exists())

    def test_adapter_timeout_and_lost_public_feedback_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = family(root / 'task', 'CUSTOM')
            calls = []

            def adapter(command, **kwargs):
                calls.append(kwargs['timeout'])
                packet = json.loads(kwargs['input'])
                response = {key: '# generated ' + key for key in packet['schema']['required']}
                return types.SimpleNamespace(stdout=json.dumps(response), stderr='', check_returncode=lambda: None)

            reports = [{'status': 'check_error'}, {'status': 'candidate_invalid'}, {'status': 'scored', 'score': 1.0}]
            with mock.patch.object(pilot.subprocess, 'run', side_effect=adapter), \
                 mock.patch.object(pilot, 'source_hashes', return_value={'fixture': 'hash'}), \
                 mock.patch.object(pilot, 'check', side_effect=reports), contextlib.redirect_stdout(io.StringIO()):
                pilot.main(['--task-root', str(task), '--mode', 'centralized', '--output', str(root / 'output'),
                            '--adapter-command', 'mock-adapter'])
            self.assertEqual(calls, [480] * 6)
            summary = json.loads((root / 'output' / 'summary.json').read_text())
            self.assertEqual(summary['status'], 'scored')
            self.assertTrue(summary['infrastructure_affected'])
            self.assertEqual(summary['inference_timeout_seconds'], 480)

    def test_failed_adapter_sidecar_is_retained_in_failure_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = family(root / 'task', 'CUSTOM')

            def adapter(command, **kwargs):
                packet = json.loads(kwargs['input'])
                path = Path(packet['metadata_path'])
                self.assertTrue(path.is_absolute())
                self.assertEqual(json.loads((path.parent / 'request.json').read_text()), packet)
                path.write_text(json.dumps({'status': 'failed', 'usage_complete': False,
                                            'usage': [{'input_tokens': 100, 'output_tokens': 20}]}))
                def failure():
                    raise RuntimeError('adapter refused malformed completion')
                return types.SimpleNamespace(stdout='', stderr='failure detail', check_returncode=failure)

            with mock.patch.object(pilot.subprocess, 'run', side_effect=adapter), \
                 mock.patch.object(pilot, 'source_hashes', return_value={'fixture': 'hash'}), \
                 self.assertRaisesRegex(RuntimeError, 'adapter refused'):
                pilot.main(['--task-root', str(task), '--mode', 'centralized', '--output', str(root / 'output'),
                            '--inference-timeout', '1800', '--adapter-command', 'mock-adapter'])
            failure = json.loads((root / 'output' / 'failure.json').read_text())
            self.assertEqual(failure['status'], 'incomplete')
            self.assertEqual(failure['usage']['total_input_plus_output'], 120)
            self.assertEqual(failure['usage']['calls_marked_incomplete_usage'], 1)


if __name__ == '__main__':
    unittest.main()

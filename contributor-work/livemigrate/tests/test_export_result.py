"""Public result export: success, failure, provenance, accounting, and privacy."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('livemigrate_export_test', CORE / 'pilot' / 'export_result.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
REVISION = 'a' * 40


def write(path, value):
    path.write_text(json.dumps(value))


def fixture(root):
    root.mkdir()
    (root / 'candidate-1').mkdir()
    hashes = {}
    for role in ('db', 'api', 'consumer'):
        code = ('# ' + role + '\ndef implementation(conn):\n    return None\n').encode()
        (root / 'candidate-1' / (role + '.py')).write_bytes(code)
        hashes[role] = hashlib.sha256(code).hexdigest()
    write(root / 'candidate-sha256.json', hashes)
    write(root / 'source-sha256.json', {'runtime.py': 'b' * 64, '../relayrepair/pilot/codex_runner.py': 'c' * 64})
    report = {'suite': 'public', 'status': 'scored', 'score': 1.0, 'passed': 1, 'total': 1,
              'cases': [{'name': 'example', 'status': 'scored', 'passed': True, 'score': 1.0,
                         'static': {'passed': True, 'violations': []},
                         'trace': {'passed': True, 'violations': [], 'physical_effects': 2},
                         'completion': {'passed': True, 'completed_steps': 3, 'total_steps': 3}}]}
    for stage in range(2):
        write(root / ('public-' + str(stage) + '.json'), report)
    heldout = dict(report, suite='heldout')
    write(root / 'heldout.json', heldout)
    write(root / 'summary.json', {'status': 'scored', 'mode': 'team', 'calls': 2, 'generation_completed': True,
          'requested_model': 'gpt-example', 'reasoning_effort': 'high', 'candidate_sha256': hashes,
          'public': [report, report], 'heldout': heldout, 'task_root': '/Users/private/task',
          'core_root': '/Users/private/core', 'messages': 'PRIVATE_TEAM_MESSAGE', 'reasoning': 'PRIVATE_REASONING',
          'usage': {'reported_totals': {'input_tokens': 20, 'output_tokens': 10, 'cached_input_tokens': 8, 'reasoning_output_tokens': 6}}})
    for index in range(2):
        call = root / ('call-%02d' % index)
        call.mkdir()
        write(call / 'metadata.json', {'status': 'completed', 'model_requested': 'gpt-example',
            'reasoning_effort': 'high', 'tool_free': True, 'return_code': 0,
            'usage': [{'input_tokens': 10, 'output_tokens': 5, 'cached_input_tokens': 4, 'reasoning_output_tokens': 3}],
            'private_field': '/Users/private/raw', 'message': 'PRIVATE_GENERATED_MESSAGE'})
        (call / 'prompt.txt').write_text('PRIVATE_PROMPT')
        (call / 'events.jsonl').write_text('PRIVATE_REASONING')
        write(call / 'response.json', {'message': 'PRIVATE_GENERATED_MESSAGE'})
    return root


class ExportTests(unittest.TestCase):
    def test_reservation_history_faults_counts_and_timeout_are_allowlisted(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixture(base / 'run')
            summary = json.loads((run / 'summary.json').read_text())
            summary.update(check_timeout_seconds=900, scaffold_sha256='d' * 64)
            for report in summary['public'] + [summary['heldout']]:
                case = report['cases'][0]
                case['history'] = {'passed': False, 'reason': 'not_linearizable', 'explored': 18,
                                   'exhaustive': True, 'raw_calls': 'PRIVATE_HISTORY /Users/private/state'}
                case['faults'] = {'lost_output': True, 'lost_effect_ack': False, 'replayed_packets': 20,
                                 'lost_output_trigger': {'step': 80, 'node': 'source', 'input_kind': 'move',
                                                        'sku': 'X', 'body': 'PRIVATE_MESSAGE'}}
                case['completion'].update(resolved_calls=6, total_calls=6, fair_rounds=95,
                                          queued_messages=2, private_state='/Users/private/database')
                case['trace'].update(violation_count=3, physical_fulfillments=4)
            summary['heldout'].update(status='unscored', score=None)
            summary['heldout']['cases'][0].update(status='candidate_invalid', score=None)
            write(run / 'summary.json', summary)
            result = exporter.export(run, base / 'export', REVISION)
            self.assertEqual(result['run']['check_timeout_seconds'], 900)
            self.assertEqual(result['run']['scaffold_sha256'], 'd' * 64)
            self.assertTrue(result['validity']['candidate_invalid'])
            for report in [entry['outcome'] for entry in result['public']] + [result['heldout']]:
                case = report['cases'][0]
                self.assertEqual(case['history'], {'passed': False, 'reason': 'not_linearizable',
                                                  'explored': 18, 'exhaustive': True})
                self.assertEqual(case['faults']['lost_output_trigger'],
                                 {'step': 80, 'node': 'source', 'input_kind': 'move', 'sku': 'X'})
                self.assertEqual(case['completion']['resolved_calls'], 6)
                self.assertEqual(case['trace']['violation_count'], 3)
                self.assertEqual(case['trace']['physical_fulfillments'], 4)
            self.assertNotIn('PRIVATE_', json.dumps(result))
            self.assertNotIn('/Users/private', json.dumps(result))

    def test_reservation_extensions_reject_wrong_types_and_unknown_labels(self):
        result = exporter.outcome({'cases': [{
            'history': {'passed': 'PRIVATE', 'exhaustive': 1, 'explored': True, 'reason': '/Users/private'},
            'faults': {'lost_output': 1, 'lost_effect_ack': 'PRIVATE', 'replayed_packets': -1,
                       'lost_output_trigger': {'step': 'PRIVATE', 'node': '/Users/private',
                                              'input_kind': 'PRIVATE_BODY', 'sku': 'PRIVATE_SKU'}},
            'completion': {'resolved_calls': True, 'total_calls': 'PRIVATE', 'fair_rounds': -1},
        }]})
        row = result['cases'][0]
        self.assertEqual(row['history'], {})
        self.assertEqual(row['faults'], {'lost_output_trigger': {}})
        self.assertEqual(row['completion'], {})

    def test_local_model_selection_provenance_survives_summary_and_call_export(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixture(base / 'run')
            summary = json.loads((run / 'summary.json').read_text())
            summary.update(requested_model='gpt-6-sol', reasoning_effort='ultra',
                           model_selection_source='local_model_argument')
            write(run / 'summary.json', summary)
            for path in run.glob('call-*/metadata.json'):
                metadata = json.loads(path.read_text())
                metadata.update(model_requested='gpt-6-sol', reasoning_effort='ultra',
                                model_selection_source='local_model_argument')
                write(path, metadata)
            result = exporter.export(run, base / 'export', REVISION)
            self.assertEqual(result['model']['requested_identifier'], 'gpt-6-sol')
            self.assertEqual(result['model']['model_selection_source'], 'local_model_argument')
            self.assertEqual(result['model']['metadata_selection_sources'], ['local_model_argument'])
            self.assertTrue(all(call['model_selection_source'] == 'local_model_argument' for call in result['calls']))
            (run / 'summary.json').unlink()
            write(run / 'failure.json', {'status': 'incomplete', 'requested_model': 'gpt-6-sol',
                  'reasoning_effort': 'ultra', 'model_selection_source': 'local_model_argument',
                  'infrastructure_affected': True})
            failed = exporter.export(run, base / 'failure-export', REVISION)
            self.assertEqual(failed['model']['model_selection_source'], 'local_model_argument')
            self.assertTrue(failed['validity']['infrastructure_affected'])

    def test_failure_without_call_metadata_retains_intended_model_and_unknown_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = base / 'run'
            run.mkdir()
            write(run / 'failure.json', {'status': 'incomplete', 'error': 'LocalInferenceInfrastructureError',
                  'failure_category': 'infrastructure', 'infrastructure_affected': True,
                  'requested_model': 'gpt-6-sol', 'reasoning_effort': 'ultra',
                  'model_selection_source': 'local_model_argument'})
            result = exporter.export(run, base / 'export', REVISION)
            self.assertEqual(result['model']['requested_identifier'], 'gpt-6-sol')
            self.assertEqual(result['model']['reasoning_effort'], 'ultra')
            self.assertEqual(result['model']['model_selection_source'], 'local_model_argument')
            self.assertEqual(result['validity']['failure_category'], 'infrastructure')
            self.assertTrue(result['validity']['infrastructure_affected'])
            self.assertFalse(result['usage']['complete'])
            self.assertIsNone(result['usage']['total_input_plus_output'])
            self.assertIsNone(result['usage']['known_input_plus_output'])
            self.assertEqual(result['calls'], [])

    def test_success_preserves_scores_code_and_complete_usage_without_private_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixture(base / 'run')
            output = base / 'export'
            result = exporter.export(run, output, REVISION)
            self.assertEqual(result['source_revision'], REVISION)
            self.assertEqual(result['model']['requested_identifier'], 'gpt-example')
            self.assertEqual(result['heldout']['score'], 1.0)
            self.assertEqual(len(result['public']), 2)
            self.assertTrue(result['usage']['complete'])
            self.assertEqual(result['usage']['total_input_plus_output'], 30)
            self.assertEqual(result['usage']['reported_totals']['cached_input_tokens'], 8)
            self.assertEqual(result['usage']['reported_totals']['reasoning_output_tokens'], 6)
            self.assertTrue(result['candidate']['recorded_hashes_verified'])
            names = sorted(str(p.relative_to(output)) for p in output.rglob('*') if p.is_file())
            self.assertEqual(names, ['candidate/api.py', 'candidate/consumer.py', 'candidate/db.py', 'result.json', 'source-sha256.json'])
            contents = '\n'.join(p.read_text() for p in output.rglob('*') if p.is_file())
            self.assertNotIn('PRIVATE_', contents)
            self.assertNotIn('/Users/private', contents)
            for role in exporter.ROLES:
                self.assertEqual((output / 'candidate' / (role + '.py')).read_bytes(), (run / 'candidate-1' / (role + '.py')).read_bytes())

    def test_failed_checks_keep_outcomes_and_violation_codes_without_raw_error_text(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixture(base / 'run')
            summary = json.loads((run / 'summary.json').read_text())
            summary['public'][0] = {'status': 'check_error', 'exit_code': 1, 'stderr': 'PRIVATE_PROMPT /Users/private/path'}
            failed = summary['heldout']
            failed.update(score=0.0, passed=0)
            failed['cases'][0].update(score=0.0, passed=False)
            failed['cases'][0]['trace'] = {'passed': False, 'violations': [
                {'code': 'incorrect_request_result', 'step': 3, 'observed': 'PRIVATE_GENERATED_MESSAGE', 'expected': '/Users/private/expected'}]}
            write(run / 'summary.json', summary)
            result = exporter.export(run, base / 'export', REVISION)
            self.assertEqual(result['heldout']['score'], 0.0)
            self.assertTrue(result['validity']['infrastructure_affected'])
            violation = result['heldout']['cases'][0]['trace']['violations'][0]
            self.assertEqual(violation['code'], 'incorrect_request_result')
            self.assertTrue(violation['details_omitted'])
            self.assertNotIn('PRIVATE_', json.dumps(result))
            self.assertNotIn('/Users/private', json.dumps(result))

    def test_incomplete_run_reports_unknown_usage_and_no_invented_final_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = base / 'run'
            run.mkdir()
            write(run / 'failure.json', {'status': 'incomplete', 'error': 'TimeoutExpired', 'message': '/Users/private/command'})
            (run / 'call-00').mkdir()
            write(run / 'call-00' / 'metadata.json', {'status': 'timeout', 'usage_complete': False})
            result = exporter.export(run, base / 'export', REVISION)
            self.assertEqual(result['run']['status'], 'incomplete')
            self.assertFalse(result['usage']['complete'])
            self.assertIsNone(result['usage']['total_input_plus_output'])
            self.assertIsNone(result['usage']['known_input_plus_output'])
            self.assertEqual(result['usage']['calls_with_unknown_usage'], 1)
            self.assertIsNone(result['model']['requested_identifier'])
            self.assertIsNone(result['validity']['generation_completed'])
            self.assertFalse(result['candidate']['available'])
            self.assertEqual(result['heldout']['status'], 'not_recorded')

    def test_absolute_candidate_paths_rejected_even_when_escaped_and_hash_correct(self):
        for source in ('# local /Users/private/work\n', 'ROOT = "\\x2fUsers\\x2fprivate"\n', 'ROOT = r"C:\\Users\\private"\n'):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                run = fixture(base / 'run')
                (run / 'candidate-1' / 'db.py').write_text(source)
                hashes = json.loads((run / 'candidate-sha256.json').read_text())
                hashes['db'] = hashlib.sha256(source.encode()).hexdigest()
                write(run / 'candidate-sha256.json', hashes)
                summary = json.loads((run / 'summary.json').read_text())
                summary['candidate_sha256'] = hashes
                write(run / 'summary.json', summary)
                with self.assertRaisesRegex(exporter.ExportError, 'absolute filesystem path'):
                    exporter.export(run, base / 'export', REVISION)
                self.assertFalse((base / 'export').exists())

    def test_tampering_and_existing_destination_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixture(base / 'run')
            output = base / 'export'
            output.mkdir()
            (output / 'keep').write_text('unchanged')
            with self.assertRaisesRegex(exporter.ExportError, 'already exists'):
                exporter.export(run, output, REVISION)
            self.assertEqual((output / 'keep').read_text(), 'unchanged')
            with self.assertRaisesRegex(exporter.ExportError, 'outside the original run'):
                exporter.export(run, run / 'export', REVISION)
            (run / 'candidate-1' / 'db.py').write_text('# tampered\n')
            with self.assertRaisesRegex(exporter.ExportError, 'does not match'):
                exporter.export(run, base / 'other', REVISION)
            self.assertFalse((base / 'other').exists())

    def test_missing_call_metadata_and_summary_disagreement_prevent_complete_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixture(base / 'run')
            (run / 'call-01' / 'metadata.json').unlink()
            result = exporter.export(run, base / 'export', REVISION)
            self.assertFalse(result['usage']['complete'])
            self.assertFalse(result['usage']['summary_totals_match'])
            self.assertIsNone(result['usage']['total_input_plus_output'])
            self.assertEqual(result['usage']['known_input_plus_output'], 15)

    def test_future_adapter_counts_need_completeness_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = fixture(base / 'run')
            path = run / 'call-01' / 'metadata.json'
            metadata = json.loads(path.read_text())
            metadata.pop('tool_free')
            metadata.pop('return_code')
            metadata['status'] = 'invalid'
            write(path, metadata)
            result = exporter.export(run, base / 'unknown', REVISION)
            self.assertFalse(result['usage']['complete'])
            self.assertEqual(result['usage']['known_input_plus_output'], 30)
            metadata['usage_complete'] = True
            write(path, metadata)
            result = exporter.export(run, base / 'accounted-failure', REVISION)
            self.assertTrue(result['usage']['complete'])
            self.assertEqual(result['calls'][1]['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()

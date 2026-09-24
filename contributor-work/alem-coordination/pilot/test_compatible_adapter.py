"""Synthetic transport tests only: no HTTP, GPU, model calls or model scores."""
import copy
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('alem_compatible_adapter_test', ROOT / 'compatible_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class CompatibleAdapterTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT.parents[1] / 'livemigrate/compute/qwen38.json').read_text())
        self.packet = {'prompt': 'Public controller task; synthetic test only.',
                       'schema': copy.deepcopy(adapter.CONTROLLER_SCHEMA),
                       'metadata_path': 'private-operator-metadata.json'}
        self.response = {'prompt_token_ids': [10, 20], 'usage': {
            'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5,
            'prompt_tokens_details': {'cached_tokens': 1},
            'completion_tokens_details': {'reasoning_tokens': 2}},
            'choices': [{'token_ids': [30, 40, 50], 'finish_reason': 'stop',
                         'message': {'content': json.dumps({'controller': '# synthetic stub', 'note': 'NOT A MODEL RESULT'})}}]}
        self.paths = []

    def transport(self, endpoint, path, payload, deadline):
        self.paths.append(path)
        if path == '/version':
            return {'version': self.profile['vllm_version']}
        if path == '/v1/models':
            return {'data': [{'id': self.profile['served_model_name']}]}
        if path == '/tokenize':
            self.assertEqual(payload['messages'], [{'role': 'user', 'content': self.packet['prompt']}])
            return {'count': 2, 'tokens': [10, 20], 'max_model_len': self.profile['max_model_len']}
        self.assertEqual(path, '/v1/chat/completions')
        self.assertEqual(payload['response_format']['json_schema']['schema'], adapter.CONTROLLER_SCHEMA)
        self.assertNotIn('metadata_path', json.dumps(payload))
        self.assertNotIn('tools', payload)
        self.assertNotIn('truncate_prompt_tokens', payload)
        return copy.deepcopy(self.response)

    def test_controller_schema_and_inclusive_usage_without_reasoning_leak(self):
        self.response['choices'][0]['message']['reasoning_content'] = 'PRIVATE SYNTHETIC REASONING'
        result = adapter.infer(self.packet, self.profile, self.transport)
        self.assertEqual(set(result), {'response', 'metadata'})
        self.assertEqual(set(result['response']), {'controller', 'note'})
        self.assertEqual(result['metadata']['usage'], [{'input_tokens': 2, 'output_tokens': 3,
                                                      'total_tokens': 5, 'cached_input_tokens': 1}])
        self.assertTrue(result['metadata']['usage_complete'])
        self.assertEqual(self.paths.count('/v1/chat/completions'), 1)
        self.assertNotIn('PRIVATE SYNTHETIC REASONING', json.dumps(result))
        self.assertEqual(result['metadata']['automatic_retries'], 0)

    def test_wrong_schema_rejected_before_any_transport_call(self):
        for schema in ({'type': 'object'}, {**adapter.CONTROLLER_SCHEMA, 'additionalProperties': True},
                       {**adapter.CONTROLLER_SCHEMA, 'required': ['controller']},
                       {**adapter.CONTROLLER_SCHEMA, 'properties': {'db': {'type': 'string'}}}):
            self.packet['schema'] = schema
            with self.assertRaises(ValueError):
                adapter.infer(self.packet, self.profile, self.transport)
        self.assertEqual(self.paths, [])

    def test_remote_endpoint_rejected_before_request(self):
        self.profile['endpoint'] = 'https://example.com/v1'
        with self.assertRaises(ValueError):
            adapter.infer(self.packet, self.profile, self.transport)
        self.assertEqual(self.paths, [])

    def test_context_reservation_fails_without_generation(self):
        self.profile['max_model_len'] = 100
        metadata = {}
        with self.assertRaises(RuntimeError):
            adapter.infer(self.packet, self.profile, self.transport, metadata)
        self.assertNotIn('/v1/chat/completions', self.paths)
        self.assertEqual(metadata['generation_requests_started'], 0)
        self.assertFalse(metadata['usage_complete'])

    def test_malformed_response_retains_usage_and_never_retries(self):
        self.response['choices'][0]['message']['content'] = 'not JSON'
        metadata = {}
        with self.assertRaises(ValueError):
            adapter.infer(self.packet, self.profile, self.transport, metadata)
        self.assertEqual(metadata['usage'][0]['total_tokens'], 5)
        self.assertTrue(metadata['usage_complete'])
        self.assertEqual(metadata['status'], 'invalid')
        self.assertEqual(self.paths.count('/v1/chat/completions'), 1)

    def test_token_id_mismatch_is_incomplete_accounting(self):
        self.response['choices'][0]['token_ids'] = [30]
        metadata = {}
        with self.assertRaises(RuntimeError):
            adapter.infer(self.packet, self.profile, self.transport, metadata)
        self.assertFalse(metadata['usage_complete'])
        self.assertTrue(metadata['usage_reported_complete'])
        self.assertEqual(metadata['raw_reported_usage']['completion_tokens'], 3)

    def test_truncation_tools_wrong_fields_and_wrong_types_rejected(self):
        original = copy.deepcopy(self.response)
        for mode in ('length', 'tool', 'wrong_field', 'wrong_type'):
            self.response = copy.deepcopy(original)
            message = self.response['choices'][0]['message']
            if mode == 'length':
                self.response['choices'][0]['finish_reason'] = 'length'
            elif mode == 'tool':
                message['tool_calls'] = [{'id': 'synthetic'}]
            elif mode == 'wrong_field':
                message['content'] = json.dumps({'api': '# no', 'note': 'no'})
            else:
                message['content'] = json.dumps({'controller': 42, 'note': 'no'})
            with self.assertRaises(RuntimeError):
                adapter.infer(self.packet, self.profile, self.transport)
        self.assertEqual(self.paths.count('/v1/chat/completions'), 4)

    def test_cli_failure_retains_known_usage_without_private_text(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            profile_path = folder / 'profile.json'
            profile_path.write_text(json.dumps(self.profile))
            packet = copy.deepcopy(self.packet)
            packet['metadata_path'] = str(folder / 'metadata.json')

            def failed_infer(packet, profile, metadata):
                metadata.update(status='invalid', usage=[{'input_tokens': 2, 'output_tokens': 3,
                                                         'total_tokens': 5}], usage_complete=True)
                raise RuntimeError('PRIVATE SYNTHETIC ERROR DETAILS')

            output = io.StringIO()
            with mock.patch.object(adapter, 'infer', failed_infer), mock.patch('sys.stdin', io.StringIO(json.dumps(packet))), contextlib.redirect_stdout(output):
                self.assertEqual(adapter.main([str(profile_path)]), 1)
            value = json.loads(output.getvalue())
            retained = json.loads((folder / 'metadata.json').read_text())
            self.assertIsNone(value['response'])
            self.assertEqual(value['metadata'], retained)
            self.assertEqual(retained['usage'][0]['total_tokens'], 5)
            self.assertEqual(retained['error_type'], 'RuntimeError')
            self.assertNotIn('PRIVATE SYNTHETIC ERROR DETAILS', output.getvalue())


if __name__ == '__main__':
    unittest.main()

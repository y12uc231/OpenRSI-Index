import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_vllm_adapter', ROOT / 'pilot' / 'compatible_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / 'compute' / 'qwen38.json').read_text())
        self.packet = {'prompt': 'Implement the public task', 'schema': {
            'type': 'object', 'properties': {'db': {'type': 'string'}, 'message': {'type': 'string'}},
            'required': ['db', 'message'], 'additionalProperties': False}}
        self.response = {'prompt_token_ids': [11, 22], 'usage': {
            'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5,
            'prompt_tokens_details': {'cached_tokens': 1}}, 'choices': [{
                'token_ids': [33, 44, 55], 'finish_reason': 'stop',
                'message': {'content': json.dumps({'db': '# source', 'message': 'ready'})}}]}
        self.paths = []

    def transport(self, endpoint, path, payload, deadline):
        self.paths.append(path)
        if path == '/version':
            return {'version': self.profile['vllm_version']}
        if path == '/v1/models':
            return {'data': [{'id': self.profile['served_model_name']}]}
        if path == '/tokenize':
            self.assertTrue(payload['chat_template_kwargs']['enable_thinking'])
            return {'count': 2, 'tokens': [11, 22], 'max_model_len': 32768}
        self.assertEqual(path, '/v1/chat/completions')
        self.assertTrue(payload['return_token_ids'])
        self.assertNotIn('metadata_path', payload)
        self.assertNotIn('truncate_prompt_tokens', payload)
        return copy.deepcopy(self.response)

    def test_exact_usage_and_no_reasoning_returned(self):
        self.response['choices'][0]['message']['reasoning_content'] = 'local-only reasoning'
        result = adapter.infer(self.packet, self.profile, self.transport)
        self.assertTrue(result['metadata']['usage_complete'])
        self.assertEqual(result['metadata']['usage'][0]['total_tokens'], 5)
        self.assertEqual(result['metadata']['usage'][0]['cached_input_tokens'], 1)
        self.assertNotIn('local-only reasoning', json.dumps(result))
        self.assertEqual(self.paths.count('/v1/chat/completions'), 1)

    def test_loopback_only_and_no_embedded_credentials(self):
        for url in ['https://example.com/v1', 'http://user:pass@localhost/v1', 'http://127.0.0.1/v1?q=x']:
            with self.assertRaises(ValueError):
                adapter.origin(url)
        self.assertEqual(adapter.origin('http://localhost:8000/v1')[1], '127.0.0.1')

    def test_context_failure_never_generates(self):
        self.profile['max_model_len'] = 10
        with self.assertRaises(RuntimeError):
            adapter.infer(self.packet, self.profile, self.transport)
        self.assertNotIn('/v1/chat/completions', self.paths)

    def test_invalid_content_preserves_consumed_usage_without_retry(self):
        self.response['choices'][0]['message']['content'] = 'not JSON'
        metadata = {}
        with self.assertRaises(ValueError):
            adapter.infer(self.packet, self.profile, self.transport, metadata)
        self.assertEqual(metadata['usage'][0]['total_tokens'], 5)
        self.assertEqual(metadata['generation_requests_started'], 1)
        self.assertEqual(metadata['status'], 'invalid')
        self.assertEqual(self.paths.count('/v1/chat/completions'), 1)

    def test_inclusive_token_mismatch_is_not_complete_accounting(self):
        self.response['choices'][0]['token_ids'] = [33]
        metadata = {}
        with self.assertRaises(RuntimeError):
            adapter.infer(self.packet, self.profile, self.transport, metadata)
        self.assertFalse(metadata['usage_complete'])
        self.assertTrue(metadata['usage_reported_complete'])
        self.assertEqual(metadata['raw_reported_usage']['completion_tokens'], 3)

    def test_refusal_truncation_and_prompt_mismatch_rejected(self):
        original = copy.deepcopy(self.response)
        for mode in ('refusal', 'length', 'prompt'):
            self.response = copy.deepcopy(original)
            if mode == 'refusal':
                self.response['choices'][0]['message']['refusal'] = 'refused'
            elif mode == 'length':
                self.response['choices'][0]['finish_reason'] = 'length'
            else:
                self.response['prompt_token_ids'] = [11, 99]
            with self.assertRaises(RuntimeError):
                adapter.infer(self.packet, self.profile, self.transport)


if __name__ == '__main__':
    unittest.main()

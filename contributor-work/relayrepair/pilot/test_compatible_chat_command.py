"""Offline HTTP doubles only: no network, provider API, or real credentials."""
import io
import json
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

from codex_runner import batch_schema
from compatible_chat_command import complete, NoRedirect


class Response(io.BytesIO):
    status = 200


class CompatibleCommandTests(unittest.TestCase):
    def setUp(self):
        self.request = {'messages': [{'role': 'user', 'content': 'synthetic'}],
                        'model': 'requested', 'params': {}, 'schema': batch_schema('plan_id')}
        self.env = {'RELAYREPAIR_BASE_URL': 'https://openrouter.ai/api/v1',
                    'RELAYREPAIR_API_KEY': 'DUMMY_OFFLINE_KEY_NOT_REAL'}
        self.payload = {'model': 'reported-version', 'usage': {'completion_tokens': 4},
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(
                {'results': [{'case_id': 'case1', 'plan_id': 'P1'}]})}}]}

    def opener(self):
        opener = Mock()
        opener.open.return_value = Response(json.dumps(self.payload).encode())
        return opener

    def test_valid_request_is_strict_and_one_call(self):
        opener = self.opener()
        result = complete(self.request, self.env, opener)
        self.assertEqual(result['model'], 'reported-version')
        opener.open.assert_called_once()
        request = opener.open.call_args.args[0]
        body = json.loads(request.data)
        self.assertTrue(body['response_format']['json_schema']['strict'])
        self.assertEqual(body['provider'], {'require_parameters': True, 'allow_fallbacks': False})
        self.assertNotIn('tools', body)
        self.assertNotIn('plugins', body)
        self.assertFalse(body['stream'])
        self.assertEqual(body['n'], 1)

    def test_http_error_does_not_retry(self):
        opener = Mock()
        opener.open.side_effect = HTTPError('https://unprinted.invalid', 429, 'PRIVATE_BODY', {}, None)
        with self.assertRaisesRegex(ValueError, 'HTTP 429'):
            complete(self.request, self.env, opener)
        opener.open.assert_called_once()

    def test_truncation_is_rejected(self):
        self.payload['choices'][0]['finish_reason'] = 'length'
        with self.assertRaisesRegex(ValueError, 'truncated'):
            complete(self.request, self.env, self.opener())

    def test_tools_and_refusals_rejected_even_with_stop(self):
        for field, value in [('tool_calls', [{'id': 'not-executed'}]), ('refusal', 'refused')]:
            with self.subTest(field=field):
                self.payload['choices'][0]['message'][field] = value
                with self.assertRaisesRegex(ValueError, 'Tool output or refusal'):
                    complete(self.request, self.env, self.opener())
                del self.payload['choices'][0]['message'][field]

    def test_override_rejected_before_request(self):
        for field in ['messages', 'model', 'tools', 'api_key', 'provider', 'plugins', 'response_format']:
            with self.subTest(field=field):
                self.request['params'] = {field: 'not-permitted'}
                opener = Mock()
                with self.assertRaises(ValueError):
                    complete(self.request, self.env, opener)
                opener.open.assert_not_called()

    def test_no_default_endpoint_and_loopback_support(self):
        opener = Mock()
        with self.assertRaisesRegex(ValueError, 'explicitly'):
            complete(self.request, {}, opener)
        opener.open.assert_not_called()
        complete(self.request, {'RELAYREPAIR_BASE_URL': 'http://127.0.0.1:8000/v1'}, self.opener())

    def test_redirect_handler_refuses_following(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, 'redirect', {}, 'https://elsewhere.invalid'))


if __name__ == '__main__':
    unittest.main()

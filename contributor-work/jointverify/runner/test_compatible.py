"""Mock-only adapter tests: no endpoint, model, credentials, or downloads."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from runner import compatible as adapter
from runner.worker import ACTION_SCHEMA
from policies.budget import BudgetLedger


ACTION = {'action': 'message', 'command': '', 'message': 'Interface ready.', 'summary': 'Coordinating'}


def fixtures(prompt_count=3, completion_count=20):
    tokens = list(range(prompt_count))
    tokenized = {'count': prompt_count, 'tokens': tokens, 'max_model_len': 32768}
    response = {'model': adapter.MODEL, 'prompt_token_ids': tokens,
                'choices': [{'index': 0, 'finish_reason': 'stop', 'token_ids': list(range(completion_count)),
                             'message': {'role': 'assistant', 'content': json.dumps(ACTION)}}],
                'usage': {'prompt_tokens': prompt_count, 'completion_tokens': completion_count,
                          'total_tokens': prompt_count + completion_count}}
    return [{'version': adapter.SERVER_VERSION}, tokenized, response]


class CompatibleTests(unittest.TestCase):
    def run_infer(self, responses=None, **kwargs):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / 'call'
        transport = patch.object(adapter, '_request_json', side_effect=responses or fixtures())
        request = transport.start()
        self.addCleanup(transport.stop)
        try:
            action = adapter.infer('Task with visible observations.', output, ACTION_SCHEMA, **kwargs)
            error = None
        except Exception as exc:
            action, error = None, exc
        return action, error, json.loads((output / 'metadata.json').read_text()), request, output

    def test_success_and_actual_template_preflight(self):
        reservations = []
        action, error, metadata, transport, output = self.run_infer(on_preflight=reservations.append, remaining_tokens=5000)
        self.assertIsNone(error)
        self.assertEqual(action, ACTION)
        self.assertEqual(metadata['usage'], [{'input_tokens': 3, 'output_tokens': 20, 'total_tokens': 23}])
        self.assertEqual(metadata['automatic_retries'], 0)
        self.assertEqual(metadata['generation_requests_started'], 1)
        self.assertEqual(reservations, [{'input_upper_bound': 3, 'output_token_limit': 4096,
                                        'reservation_tokens': 4099, 'context_limit': 32768}])
        token_request = transport.call_args_list[1].args[1]
        generation = transport.call_args_list[2].args[1]
        self.assertTrue(transport.call_args_list[1].args[0].endswith(':8000/tokenize'))
        for key in ['model', 'messages', 'add_generation_prompt', 'continue_final_message', 'add_special_tokens']:
            self.assertEqual(token_request[key], generation[key])
        self.assertNotIn('tools', generation)
        self.assertNotIn('truncate_prompt_tokens', generation)
        self.assertTrue(generation['return_token_ids'])
        self.assertEqual(generation['max_completion_tokens'], 4096)
        self.assertEqual(json.loads((output / 'response.json').read_text()), ACTION)

    def test_localhost_normalization_and_remote_endpoint_rejection(self):
        self.assertEqual(adapter.endpoint('http://localhost:9000/v1/'), 'http://127.0.0.1:9000/v1')
        self.assertEqual(adapter.endpoint('http://[::1]:8000/v1'), 'http://[::1]:8000/v1')
        for endpoint in ['https://api.openai.com/v1', 'http://localhost.example/v1', 'http://127.0.0.1/v1?key=secret',
                         'http://user:secret@localhost/v1', 'file:///v1', 'http://127.0.0.1/proxy/v1']:
            with self.subTest(endpoint=endpoint), self.assertRaises(adapter.PreflightError):
                adapter.endpoint(endpoint)

    def test_remote_environment_rejected_before_requests(self):
        with patch.dict(os.environ, {'JOINTVERIFY_BASE_URL': 'https://remote.example/v1'}):
            _, error, metadata, request, _ = self.run_infer()
        self.assertIsInstance(error, adapter.PreflightError)
        self.assertEqual(request.call_count, 0)
        self.assertEqual(metadata['generation_requests_started'], 0)

    def test_context_boundary_and_no_truncation(self):
        _, error, _, transport, _ = self.run_infer(fixtures(32768 - 4096))
        self.assertIsNone(error)
        self.assertEqual(transport.call_count, 3)
        _, error, metadata, transport, _ = self.run_infer(fixtures(32768 - 4096 + 1))
        self.assertIsInstance(error, adapter.PreflightError)
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(metadata['generation_requests_started'], 0)

    def test_shared_reservation_rejects_before_generation(self):
        _, error, metadata, transport, _ = self.run_infer(remaining_tokens=4098)
        self.assertIsInstance(error, adapter.PreflightError)
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(metadata['generation_requests_started'], 0)

    def test_ledger_callback_can_stop_generation(self):
        def refuse(_):
            raise RuntimeError('Shared call pool exhausted')
        _, error, metadata, transport, _ = self.run_infer(on_preflight=refuse)
        self.assertEqual(str(error), 'Shared call pool exhausted')
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(metadata['generation_requests_started'], 0)

    def test_real_ledger_reserves_before_generation_and_settles_failed_output(self):
        ledger = BudgetLedger(max_calls=1, max_total_tokens=5000)
        tickets = []
        def reserve(info):
            tickets.append(ledger.reserve_call(input_upper_bound=info['input_upper_bound'],
                                               output_token_limit=info['output_token_limit']))
        responses = fixtures()
        responses[2]['choices'][0]['finish_reason'] = 'length'
        _, error, metadata, _, _ = self.run_infer(responses, on_preflight=reserve, remaining_tokens=5000)
        self.assertIsInstance(error, adapter.InferenceError)
        ledger.settle_call(tickets[0], metadata['usage'][0])
        summary = ledger.summary()
        self.assertEqual(summary['calls_started'], 1)
        self.assertEqual(summary['total_tokens'], 23)
        self.assertEqual(summary['token_budget_mode'], 'bounded_reservations')
        self.assertTrue(summary['token_telemetry_valid'])

    def test_missing_usage_and_prompt_mismatch_fail(self):
        for change in ['no_usage', 'different_prompt', 'different_output_count', 'bad_total', 'wrong_model']:
            responses = fixtures()
            response = responses[2]
            if change == 'no_usage': del response['usage']
            if change == 'different_prompt': response['prompt_token_ids'][0] = 1000; responses[1]['tokens'] = [0, 1, 2]
            if change == 'different_output_count': response['choices'][0]['token_ids'].pop()
            if change == 'bad_total': response['usage']['total_tokens'] += 1
            if change == 'wrong_model': response['model'] = 'another-model'
            with self.subTest(change=change):
                _, error, metadata, transport, _ = self.run_infer(responses)
                self.assertIsInstance(error, adapter.InferenceError)
                self.assertEqual(metadata['generation_requests_started'], 1)
                self.assertEqual(transport.call_count, 3)

    def test_truncated_refused_and_native_tool_calls_rejected_with_usage(self):
        for change in ['length', 'refusal', 'tool']:
            responses = fixtures()
            choice = responses[2]['choices'][0]
            if change == 'length': choice['finish_reason'] = 'length'
            if change == 'refusal': choice['message']['refusal'] = 'Refused'
            if change == 'tool': choice['message']['tool_calls'] = [{'function': 'execute'}]; choice['finish_reason'] = 'tool_calls'
            with self.subTest(change=change):
                _, error, metadata, _, _ = self.run_infer(responses)
                self.assertIsInstance(error, adapter.InferenceError)
                self.assertTrue(metadata['usage_complete'])
                self.assertEqual(metadata['usage'][0]['output_tokens'], 20)
                if change == 'tool': self.assertFalse(metadata['tool_free'])

    def test_reasoning_and_cached_tokens_counted_once_in_inclusive_totals(self):
        responses = fixtures()
        responses[2]['choices'][0]['message']['reasoning_content'] = 'Hidden reasoning counts in the generated IDs.'
        responses[2]['usage']['completion_tokens_details'] = {'reasoning_tokens': 12}
        responses[2]['usage']['prompt_tokens_details'] = {'cached_tokens': 2}
        _, error, metadata, _, _ = self.run_infer(responses)
        self.assertIsNone(error)
        self.assertEqual(metadata['usage'][0], {'input_tokens': 3, 'output_tokens': 20, 'total_tokens': 23,
                                              'reasoning_tokens': 12, 'cached_input_tokens': 2})

    def test_bad_json_actions_are_not_repaired_or_retried(self):
        for content in ['```json\n{}\n```', '{"action":"finish","action":"shell"}',
                        json.dumps(dict(ACTION, command='rm something')), json.dumps(dict(ACTION, extra=True))]:
            responses = fixtures()
            responses[2]['choices'][0]['message']['content'] = content
            with self.subTest(content=content):
                _, error, metadata, transport, _ = self.run_infer(responses)
                self.assertIsNotNone(error)
                self.assertTrue(metadata['usage_complete'])
                self.assertEqual(transport.call_count, 3)

    def test_transport_failure_has_one_charged_attempt_and_unknown_usage(self):
        responses = fixtures()[:2] + [TimeoutError('Local inference timed out')]
        _, error, metadata, transport, _ = self.run_infer(responses)
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual(metadata['status'], 'timeout')
        self.assertEqual(metadata['generation_requests_started'], 1)
        self.assertFalse(metadata['usage_complete'])
        self.assertEqual(metadata['usage'], [])
        self.assertEqual(transport.call_count, 3)

    def test_wrong_server_version_and_wrong_schema_send_no_generation(self):
        _, error, metadata, transport, _ = self.run_infer([{'version': 'new-version'}])
        self.assertIsInstance(error, adapter.PreflightError)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(metadata['generation_requests_started'], 0)
        with self.assertRaises(adapter.PreflightError):
            adapter._schema_check({'type': 'object'})

    def test_http_redirect_is_not_followed(self):
        response = Mock(status=302)
        connection = Mock()
        connection.getresponse.return_value = response
        with patch.object(adapter.http.client, 'HTTPConnection', return_value=connection) as factory:
            with self.assertRaises(adapter.InferenceError):
                adapter._request_json('http://127.0.0.1:8000/version', None, deadline=time.monotonic() + 10)
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(connection.request.call_count, 1)
        connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()

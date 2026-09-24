"""Offline boundary checks; never load weights or contact a model server."""
import unittest
from preflight_request import prepare


class Tokenizer:
    def __init__(self, count):
        self.count = count

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize and add_generation_prompt
        return [1] * self.count


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.request = {'messages': [{'role': 'user', 'content': 'Implement the feature.'}]}

    def test_reserves_exact_template_plus_enforced_output(self):
        result = prepare(self.request, Tokenizer(16384), remaining_tokens=1_000_000)
        self.assertEqual(result['reservation_tokens'], 20480)
        self.assertEqual(result['request']['max_completion_tokens'], 4096)
        self.assertNotIn('max_tokens', result['request'])

    def test_context_boundary_includes_output(self):
        prepare(self.request, Tokenizer(28672), remaining_tokens=1_000_000)
        with self.assertRaises(ValueError):
            prepare(self.request, Tokenizer(28673), remaining_tokens=1_000_000)

    def test_budget_cannot_overreserve(self):
        with self.assertRaises(ValueError):
            prepare(self.request, Tokenizer(100), remaining_tokens=4195)

    def test_uncontrolled_prompt_fields_rejected(self):
        with self.assertRaises(ValueError):
            prepare({**self.request, 'tools': []}, Tokenizer(100), remaining_tokens=1_000_000)


if __name__ == '__main__':
    unittest.main()

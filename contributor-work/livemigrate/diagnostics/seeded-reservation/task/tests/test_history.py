import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import history


def call(name, lines, status, begin=0, end=10, rid=None):
    return {'call_id': name, 'reservation_id': rid or name, 'lines': lines,
            'invoke_step': begin, 'response_step': end, 'status': status}


class HistoryTests(unittest.TestCase):
    def test_either_concurrent_winner_is_legal_but_two_winners_are_not(self):
        for first, second in [('committed', 'out_of_stock'), ('out_of_stock', 'committed')]:
            result = history.check_history({'X': 1}, [call('a', {'X': 1}, first), call('b', {'X': 1}, second)])
            self.assertTrue(result['passed'])
            self.assertTrue(result['exhaustive'])
        result = history.check_history({'X': 1}, [call('a', {'X': 1}, 'committed'), call('b', {'X': 1}, 'committed')])
        self.assertEqual(result['reason'], 'not_linearizable')
        self.assertTrue(result['exhaustive'])

    def test_real_time_precedence_prevents_using_future_consumption(self):
        calls = [call('a', {'X': 1}, 'out_of_stock', 0, 1), call('b', {'X': 1}, 'committed', 2, 3)]
        self.assertFalse(history.check_history({'X': 1}, calls)['passed'])
        calls[0]['response_step'] = 3  # Now b can legally take stock first.
        self.assertTrue(history.check_history({'X': 1}, calls)['passed'])

    def test_atomic_bundle_failure_does_not_consume_other_stock(self):
        calls = [call('a', {'X': 1, 'Y': 1}, 'out_of_stock', 0, 1),
                 call('b', {'X': 1}, 'committed', 2, 3)]
        self.assertTrue(history.check_history({'X': 1, 'Y': 0}, calls)['passed'])
        calls[1]['status'] = 'out_of_stock'
        self.assertFalse(history.check_history({'X': 1, 'Y': 0}, calls)['passed'])

    def test_retries_preserve_receipt_without_stock_check_or_second_deduction(self):
        calls = [call('a', {'X': 1}, 'committed', 0, 1, 'shared'),
                 call('b', {'X': 1}, 'committed', 2, 3, 'shared'),
                 call('c', {'X': 1}, 'committed', 4, 5, 'new')]
        self.assertTrue(history.check_history({'X': 2}, calls)['passed'])
        self.assertFalse(history.check_history({'X': 1}, calls)['passed'])
        calls[2]['status'] = 'out_of_stock'
        self.assertTrue(history.check_history({'X': 1}, calls)['passed'])

    def test_changed_payload_conflicts_even_after_out_of_stock(self):
        calls = [call('a', {'X': 2}, 'out_of_stock', 0, 1, 'shared'),
                 call('b', {'X': 1}, 'idempotency_conflict', 2, 3, 'shared'),
                 call('c', {'X': 2}, 'out_of_stock', 4, 5, 'shared')]
        self.assertTrue(history.check_history({'X': 1}, calls)['passed'])
        calls[1]['status'] = 'committed'
        self.assertFalse(history.check_history({'X': 1}, calls)['passed'])

    def test_same_id_overlapping_conflict_has_no_predetermined_first_payload(self):
        calls = [call('a', {'X': 1}, 'idempotency_conflict', rid='same'),
                 call('b', {'X': 2}, 'committed', rid='same')]
        self.assertTrue(history.check_history({'X': 2}, calls)['passed'])

    def test_global_interleaving_can_differ_from_input_order(self):
        # B must precede A (to justify X rejection), while C precedes D in real
        # time. Calls are deliberately not presented in any serialization order.
        calls = [call('a', {'X': 1}, 'out_of_stock', 0, 9),
                 call('d', {'Y': 1}, 'out_of_stock', 4, 8),
                 call('b', {'X': 1}, 'committed', 1, 7),
                 call('c', {'Y': 1}, 'committed', 0, 3)]
        before = copy.deepcopy(calls)
        self.assertTrue(history.check_history({'X': 1, 'Y': 1}, calls)['passed'])
        self.assertEqual(calls, before)

    def test_pending_malformed_and_budget_exhaustion_are_distinct(self):
        pending = call('a', {'X': 1}, None, end=None)
        self.assertEqual(history.check_history({'X': 1}, [pending])['reason'], 'incomplete_history')
        for malformed in [call('a', {'X': True}, 'committed'), call('a', {'unknown': 1}, 'committed'),
                          call('a', {}, 'committed'), call('a', {'X': 1}, 'committed', 3, 2)]:
            self.assertEqual(history.check_history({'X': 1}, [malformed])['reason'], 'invalid_history')
        valid = call('a', {'X': 1}, 'committed')
        self.assertEqual(history.check_history({'X': 1}, [valid, valid])['reason'], 'invalid_history')
        with mock.patch.object(history, 'STATE_LIMIT', 1):
            result = history.check_history({'X': 1}, [valid])
        self.assertEqual(result['reason'], 'bound_exhausted')
        self.assertFalse(result['exhaustive'])

    def test_empty_history_and_six_independent_calls_are_exhaustively_decided(self):
        self.assertTrue(history.check_history({}, [])['passed'])
        calls = [call(str(i), {'X': 1}, 'committed') for i in range(6)]
        result = history.check_history({'X': 6}, calls)
        self.assertTrue(result['passed'])
        self.assertTrue(result['exhaustive'])
        self.assertEqual(result['explored'], 64)  # All 2**6 prefix subsets.


if __name__ == '__main__':
    unittest.main()

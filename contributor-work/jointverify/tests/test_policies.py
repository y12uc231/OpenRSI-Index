"""Policy invariants and accounting tests; no models or benchmark tasks run."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import unittest

from policies import Policy, BudgetLedger, BudgetExceeded, TelemetryError
from policies.budget import normalize_usage


def state():
    return {'workers': [
        {'id': 'left', 'turns': 1, 'done': False, 'revision': 'a1',
         'changed_paths': ['api.py'], 'exports': ['parse'], 'imports': []},
        {'id': 'right', 'turns': 1, 'done': False, 'revision': 'b1',
         'changed_paths': ['client.py'], 'exports': [], 'imports': ['parse'], 'message': 'Uses parse output.'}],
        'candidate_hash': 'new', 'verified_hash': 'old', 'last_verify_passed': True,
        'turns_since_verify': 1, 'last_worker_id': 'left',
        'worker_calls_remaining': 8, 'checks_remaining': 2,
        'verification_feedback': ''}


class PolicyTests(unittest.TestCase):
    def test_dependency_evidence_allocates_check_before_periodic_deadline(self):
        view = state()
        before = deepcopy(view)
        self.assertEqual(Policy({'mode': 'periodic', 'interval': 2}).action(view)['action'], 'worker')
        decision = Policy({'mode': 'adaptive', 'interval': 4}).action(view)
        self.assertEqual(decision['action'], 'joint_verify')
        self.assertIn('symbol dependency', decision['reason'])
        self.assertEqual(view, before)

    def test_disjoint_updates_do_not_force_adaptive_to_always_verify(self):
        view = state()
        view['workers'][1]['imports'] = []
        self.assertEqual(Policy({'mode': 'adaptive', 'interval': 4}).action(view)['action'], 'worker')
        self.assertEqual(Policy({'mode': 'always_verify'}).action(view)['action'], 'joint_verify')

    def test_no_retest_loop_for_unchanged_failure(self):
        for mode in ['periodic', 'always_verify', 'adaptive']:
            with self.subTest(mode=mode):
                view = state()
                view.update(last_verify_passed=False, candidate_hash='failed', verified_hash='failed',
                            verification_feedback='Public integration test fails.')
                decision = Policy({'mode': mode}).action(view)
                self.assertEqual(decision['action'], 'worker')
                self.assertIn('Public integration test fails.', '\n'.join(decision['message_context']))
                view['candidate_hash'] = 'repaired'
                self.assertEqual(Policy({'mode': mode}).action(view)['action'], 'joint_verify')

    def test_final_public_barrier_respects_budget_but_never_cancels_judge(self):
        view = state()
        view['worker_calls_remaining'] = 0
        policy = Policy({'mode': 'periodic'})
        self.assertEqual(policy.action(view)['action'], 'joint_verify')
        view['checks_remaining'] = 0
        decision = policy.action(view)
        self.assertEqual(decision['action'], 'finish')
        self.assertIn('Judge still required', decision['reason'])

    def test_rotation_and_shared_messages_are_common_to_controls(self):
        view = state()
        view['checks_remaining'] = 0
        view['last_worker_id'] = 'right'
        for mode in ['periodic', 'always_verify', 'adaptive']:
            decision = Policy({'mode': mode}).action(view)
            self.assertEqual(decision['worker_id'], 'left')
            self.assertIn('Uses parse output.', '\n'.join(decision['message_context']))

    def test_verified_current_hash_is_not_rechecked_due_to_old_overlap(self):
        view = state()
        view['verified_hash'] = view['candidate_hash']
        view['turns_since_verify'] = 100
        self.assertEqual(Policy({'mode': 'adaptive'}).action(view)['action'], 'worker')


class BudgetTests(unittest.TestCase):
    def test_reasoning_and_cached_tokens_are_subsets_not_extra_cost(self):
        usage = normalize_usage({'input_tokens': 100, 'output_tokens': 20,
                                 'cached_input_tokens': 40, 'reasoning_tokens': 8})
        self.assertEqual(usage['total_tokens'], 120)
        self.assertEqual(usage['reasoning_tokens'], 8)

    def test_missing_or_contradictory_telemetry_never_becomes_zero(self):
        for usage in [None, {}, {'input_tokens': 1, 'output_tokens': '3'},
                      {'input_tokens': 1, 'prompt_tokens': 2, 'output_tokens': 3},
                      {'input_tokens': 1, 'output_tokens': 3, 'reasoning_tokens': 4}]:
            with self.subTest(usage=usage):
                ledger = BudgetLedger()
                ticket = ledger.reserve_call()
                with self.assertRaises(TelemetryError):
                    ledger.settle_call(ticket, usage)
                self.assertIsNone(ledger.summary()['total_tokens'])
                self.assertEqual(ledger.summary()['calls_started'], 1)

    def test_bounded_reservations_prevent_parallel_oversubscription(self):
        ledger = BudgetLedger(max_total_tokens=75)
        def attempt():
            try:
                return ledger.reserve_call(30, 20)
            except BudgetExceeded:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sum(x is not None for x in outcomes), 1)
        ledger.settle_call(0, {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30})
        ledger.reserve_call(25, 20)
        with self.assertRaises(BudgetExceeded):
            ledger.reserve_call(1, 1)

    def test_unenforceable_output_cap_is_labeled_call_count_only(self):
        ledger = BudgetLedger(max_calls=1)
        ticket = ledger.reserve_call()
        ledger.settle_call(ticket, {'input_tokens': 50000, 'output_tokens': 15000})
        self.assertEqual(ledger.summary()['token_budget_mode'], 'call_count_only_tokens_diagnostic')
        with self.assertRaises(BudgetExceeded):
            ledger.reserve_call()
        with self.assertRaises(BudgetExceeded):
            BudgetLedger(max_total_tokens=100).reserve_call()

    def test_observed_cap_overrun_is_explicit(self):
        ledger = BudgetLedger(max_total_tokens=200)
        ticket = ledger.reserve_call(100, 10)
        with self.assertRaises(BudgetExceeded):
            ledger.settle_call(ticket, {'input_tokens': 100, 'output_tokens': 11})
        self.assertTrue(ledger.summary()['overrun'])
        self.assertEqual(ledger.summary()['total_tokens'], 111)

    def test_public_check_cap_and_all_tool_time_counted(self):
        ledger = BudgetLedger(max_checks=1)
        ordinary = ledger.start_tool()
        check = ledger.start_tool(is_check=True)
        with self.assertRaises(BudgetExceeded):
            ledger.start_tool(is_check=True)
        ledger.finish_tool(ordinary, 1.5)
        ledger.finish_tool(check, 2.0)
        self.assertEqual(ledger.summary()['total_tool_seconds'], 3.5)
        self.assertEqual(ledger.summary()['public_checks_started'], 1)

    def test_tool_time_missing_is_not_zero(self):
        ledger = BudgetLedger()
        ticket = ledger.start_tool()
        with self.assertRaises(TelemetryError):
            ledger.finish_tool(ticket, None)
        self.assertIsNone(ledger.summary()['total_tool_seconds'])


if __name__ == '__main__':
    unittest.main()

import random
import unittest

from relayrepair import (CONDITIONS, PILOT_SEEDS, evaluate_answer, generate_case,
                         parse_visible, scripted_answer, solve_structured)


class RelayRepairTests(unittest.TestCase):
    def setUp(self):
        self.cases = [generate_case(seed, i) for i, seed in enumerate(PILOT_SEEDS)]

    def test_visible_parser_matches_independent_structured_oracle(self):
        for case in self.cases:
            for condition in CONDITIONS:
                cards = case["observations"][condition]["central_cards"]
                self.assertEqual(scripted_answer(cards), case["oracle"]["answers"][condition]["plan_id"])

    def test_order_and_duplicate_invariance(self):
        rng = random.Random(7781)
        for case in self.cases:
            cards = case["observations"]["final_ordered"]["central_cards"]
            expected = scripted_answer(cards)
            for _ in range(10):
                perturbed = cards * 2
                rng.shuffle(perturbed)
                self.assertEqual(scripted_answer(perturbed), expected)

    def test_alternate_support_and_change_balance(self):
        changed = [c for c in self.cases if c["oracle"]["optimum_changed"]]
        self.assertEqual(len(changed), 4)
        for case in self.cases:
            if case["mechanism"] == "alternate_support_survives":
                self.assertFalse(case["oracle"]["optimum_changed"])
                update = case["oracle"]["update"]
                self.assertFalse(case["oracle"]["answers"]["final_ordered"]["node_truth"][update["id"]])

    def test_fallback_when_all_rules_false(self):
        case = self.cases[0]
        sources, rules, plans = parse_visible(case["observations"]["initial"]["central_cards"])
        for source in sources.values():
            source["value"] = source["threshold"] + (1 if source["op"] == "le" else -1)
        answer = solve_structured(sources, rules, plans)
        fallback = next(plan for plan in plans if plan["requires"] is None)
        self.assertEqual(answer["plan_id"], fallback["id"])
        self.assertGreater(answer["utility"], 0)

    def test_stale_arrival_failure_and_abstention(self):
        failed = 0
        for case in self.cases:
            cards = case["observations"]["final_shuffled"]["central_cards"]
            answer = scripted_answer(cards, "latest_arrival")
            failed += not evaluate_answer(case, "final_shuffled", answer)["exact_success"]
            abstain = evaluate_answer(case, "final_shuffled", None)
            self.assertFalse(abstain["valid_plan"])
            self.assertEqual(abstain["utility"], 0)
        self.assertEqual(failed, 4)

    def test_private_ownership_partition(self):
        for case in self.cases:
            for obs in case["observations"].values():
                self.assertEqual(len(obs["roles"]), 3)
                owned = sorted(card for role in obs["roles"] for card in role["private_cards"])
                central_private = sorted(obs["central_cards"][len(obs["public_cards"]):])
                self.assertEqual(owned, central_private)


if __name__ == "__main__":
    unittest.main()

"""Check that useful feedback crosses the boundary and trajectories do not."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('alem_pilot', Path(__file__).with_name('run.py'))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class FeedbackTests(unittest.TestCase):
    def test_complete_score_without_trajectory(self):
        secret = 'private per-world observation'
        source = {'status': 'scored', 'provenance_verified': True, 'total': 2, 'primary_score': 0.2,
                  'metrics_mean': {'Team/coord_reward_pct_of_max': 0.2, 'secret': secret},
                  'cases': [{'status': 'scored', 'observation': secret, 'steps': 10},
                            {'status': 'scored', 'observation': secret, 'steps': 20}]}
        result = pilot.feedback(source)
        self.assertEqual(result['primary_score'], 0.2)
        self.assertEqual(result['aggregate_costs']['steps'], 30)
        self.assertNotIn(secret, str(result))
        self.assertNotIn('cases', result)

    def test_partial_scores_are_not_accepted(self):
        source = {'status': 'scored', 'provenance_verified': True, 'total': 2, 'primary_score': 0.9,
                  'metrics_mean': {'Team/coord_reward_pct_of_max': 0.9},
                  'cases': [{'status': 'scored'}, {'status': 'candidate_invalid',
                             'diagnostic_code': 'candidate_act', 'traceback': 'private'}]}
        result = pilot.feedback(source)
        self.assertIsNone(result['primary_score'])
        self.assertEqual(result['diagnostic_counts'], {'candidate_act': 1})
        self.assertNotIn('private', str(result))


if __name__ == '__main__':
    unittest.main()

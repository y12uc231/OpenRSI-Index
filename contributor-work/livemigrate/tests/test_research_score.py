import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('research_score_test', ROOT / 'research/evaluate.py')
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)


def report(passed):
    return {'status': 'scored', 'generation_completed': True, 'infrastructure_affected': False,
            'calls': 6, 'usage': {'calls_with_usage': 6, 'calls_marked_incomplete_usage': 0,
                                'total_input_plus_output': 160000},
            'heldout': {'status': 'scored', 'total': 3, 'passed': passed,
                        'cases': [{'name': 'case-' + str(i), 'status': 'scored', 'passed': i < passed}
                                  for i in range(3)]}}


class ResearchScoreTests(unittest.TestCase):
    def test_macro_family_metric_includes_all_declared_cases(self):
        result = scoring.aggregate({'amounts': report(3), 'identity': report(0)})
        self.assertEqual(result['score'], .5)
        self.assertEqual(result['family_scores'], {'amounts': 1., 'identity': 0.})

    def test_no_family_dropping_incomplete_feedback_or_unknown_usage(self):
        self.assertIsNone(scoring.aggregate({'amounts': report(3)})['score'])
        for mutate in (
            lambda x: x.update(status='candidate_invalid'),
            lambda x: x.update(infrastructure_affected=True),
            lambda x: x['heldout']['cases'].pop(),
            lambda x: x['heldout']['cases'][0].update(passed=1),
            lambda x: x['usage'].update(calls_with_usage=5),
            lambda x: x['usage'].update(total_input_plus_output=196609),
            lambda x: x['usage'].update(total_input_plus_output=None),
        ):
            bad = copy.deepcopy(report(3))
            mutate(bad)
            self.assertIsNone(scoring.aggregate({'amounts': report(3), 'identity': bad})['score'])


if __name__ == '__main__':
    unittest.main()

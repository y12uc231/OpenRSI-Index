import unittest
import json
from unittest.mock import patch

from evaluator.checker import ROOT, checked_patch, check_judge_coverage, evaluate, get_case
from evaluator.container_check import counts


def diff(path, body='value = 1'):
    return f'diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n+{body}\n'


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.case = get_case('click2068_1_6')

    def test_judge_strips_tests_and_preserves_source(self):
        code, tests = diff('src/click/new.py'), diff('tests/test_new.py')
        kept, stripped, _ = checked_patch(code + tests, self.case, 'judge')
        self.assertEqual(kept, code)
        self.assertEqual(stripped, ['tests/test_new.py'])
        self.assertEqual(checked_patch(code + tests, self.case, 'public')[0], code + tests)

    def test_rejects_traversal_grader_configuration_and_symlink(self):
        for path in ['src/click/../../runner.sh', '.git/config', 'pyproject.toml', '/etc/passwd', 'src/click/.hidden.py']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                checked_patch(diff(path), self.case, 'judge')
        with self.assertRaises(ValueError):
            checked_patch(diff('src/click/link').replace('100644', '120000'), self.case, 'judge')

    def test_rejects_mismatched_headers(self):
        with self.assertRaises(ValueError):
            checked_patch(diff('src/click/x.py').replace('+++ b/src/click/x.py', '+++ b/tests/conftest.py'), self.case, 'public')

    def test_junit_counts_failures_errors_skips(self):
        xml = '<testsuite><testcase name="pass"/><testcase name="fail"><failure/></testcase><testcase name="error"><error/></testcase><testcase name="skip"><skipped/></testcase></testsuite>'
        actual = counts(xml)
        self.assertEqual([actual[k] for k in ['total', 'passed', 'failed', 'errors', 'skipped']], [4, 1, 1, 1, 1])

    def test_zero_or_deselected_tests_cannot_pass(self):
        check = check_judge_coverage('click2068_1_6', 1, {'passed': True, 'test_counts': counts('<testsuite/>')})
        self.assertFalse(check['passed'])

    def test_known_dynamic_uuid_identity_is_normalized_only(self):
        expected = json.loads((ROOT / 'manifests/judge-expectations-v1.json').read_text())['cases']['dirty43_2_3']['2']
        expected['case_ids'] = [s if '::test_is_uuid_true[' not in s or not s.endswith('-dirty9]') else 'tests.test_other::test_is_uuid_true[12345678-1234-1234-1234-123456789abc-dirty9]' for s in expected['case_ids']]
        self.assertTrue(check_judge_coverage('dirty43_2_3', 2, {'passed': True, 'test_counts': expected})['passed'])
        expected['case_ids'].pop()
        self.assertFalse(check_judge_coverage('dirty43_2_3', 2, {'passed': True, 'test_counts': expected})['passed'])

    def test_expired_wall_budget_launches_no_container(self):
        with patch('evaluator.checker.subprocess.run', side_effect=AssertionError('launched after deadline')):
            result = evaluate('click2068_1_6', {'lead': '', 'member': ''}, 'public', max_seconds=0)
        self.assertFalse(result['validinfra'])
        self.assertTrue(result['merge']['budget_exhausted'])

    def test_public_does_not_load_judge_assets(self):
        merge = {'validinfra': True, 'candidate_valid': True, 'merged_patch': '', 'merged_patch_sha256': 'unused'}
        check = {'validinfra': True, 'passed': True}
        with patch('evaluator.checker.asset_bytes', side_effect=AssertionError('judge asset leaked')), patch('evaluator.checker._container', side_effect=[merge, check]) as docker:
            report = evaluate('click2068_1_6', {'lead': '', 'member': ''}, 'public')
        self.assertTrue(report['public_passed'])
        self.assertNotIn('both_features_passed', report)
        self.assertTrue(all('judge.patch' not in call.args[2] for call in docker.call_args_list))
        self.assertTrue(all('oracle_patch' not in call.args[1] and 'judge_test_patches' not in call.args[1] for call in docker.call_args_list))


if __name__ == '__main__':
    unittest.main()

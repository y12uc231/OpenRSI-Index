import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


scaffold = module('scaffold_unit', ROOT / 'pilot/scaffold.py')
pilot = module('scaffold_pilot_unit', ROOT / 'pilot/run.py')


class ScaffoldTests(unittest.TestCase):
    def test_fixed_call_budget_and_no_controller_override(self):
        baseline = scaffold.load(ROOT / 'research/baseline.json')
        for change in (
            {'model': 'different'},
            {'stages': [[['db', 'api', 'consumer']]]},
            {'stages': [[['db', 'db', 'consumer']]] * 2},
            {'stages': [[['db', 'api', 'consumer', 'consumer']]] * 2},
            {'shared_instruction': 'x' * 5001},
            {'version': True},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                scaffold.validate({**baseline, **change})
        self.assertEqual(scaffold.load(ROOT / 'research/contract-first.json')['stages'][0], [['db'], ['api', 'consumer']])

    def test_wave_dependencies_feedback_and_replay_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seen = {}
            checks = []

            def infer(prompt, call_dir, output_schema, timeout):
                index = int(call_dir.name.split('-')[1])
                role = next(key for key in output_schema['required'] if key != 'message')
                seen[index] = (role, prompt)
                return {role: '# revision ' + str(index), 'message': 'message-' + str(index)}

            def check(candidate, suite, destination, task_root, timeout=180):
                checks.append((len(seen), suite))
                return {'status': 'scored', 'score': 1.0, 'marker': 'PUBLIC_FEEDBACK' if suite == 'public' else 'SECRET_FINAL'}

            backend = types.SimpleNamespace(infer=infer, MODEL='fake', EFFORT='fake')
            with mock.patch.object(pilot, 'load_backend', return_value=backend), \
                 mock.patch.object(pilot, 'source_hashes', return_value={}), \
                 mock.patch.object(pilot, 'check', side_effect=check), \
                 contextlib.redirect_stdout(io.StringIO()):
                pilot.main(['--mode', 'team', '--scaffold', str(ROOT / 'research/contract-first.json'),
                            '--output', str(root / 'out')])
            self.assertEqual(checks, [(3, 'public'), (6, 'public'), (6, 'heldout')])
            self.assertEqual([seen[i][0] for i in range(6)], ['db', 'api', 'consumer'] * 2)
            for i in (1, 2):
                self.assertIn('# revision 0', seen[i][1])
                self.assertNotIn('# revision 1', seen[i][1])
                self.assertNotIn('# revision 2', seen[i][1])
            self.assertNotIn('PUBLIC_FEEDBACK', seen[2][1])
            self.assertIn('PUBLIC_FEEDBACK', seen[3][1])
            self.assertIn('# revision 4', (root / 'out/candidate-1/api.py').read_text())
            report = json.loads((root / 'out/summary.json').read_text())
            self.assertEqual(report['calls'], 6)
            self.assertEqual(len(report['scaffold_sha256']), 64)
            self.assertEqual(json.loads((root / 'out/scaffold.json').read_text()), scaffold.load(ROOT / 'research/contract-first.json'))


if __name__ == '__main__':
    unittest.main()

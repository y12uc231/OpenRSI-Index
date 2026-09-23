"""Offline transport tests. No API calls or model inference."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import unittest

from command_runner import CommandRunner
from codex_runner import batch_schema


class CommandRunnerTests(unittest.TestCase):
    @contextmanager
    def runner(self, code, timeout=3, params=None):
        with tempfile.TemporaryDirectory(prefix='relayrepair-transport-test-') as tmp:
            root = Path(tmp)
            script = root / 'stub.py'
            script.write_text(code)
            config = root / 'config.json'
            config.write_text(json.dumps({'execution_kind': 'mock', 'model': 'NOT_A_MODEL',
                'command': [sys.executable, str(script)], 'params': params or {},
                'timeout_seconds': timeout}))
            yield CommandRunner(config), root

    def test_passes_request_and_records_reported_identity(self):
        code = '''import json,sys
r=json.load(sys.stdin)
assert r['model']=='NOT_A_MODEL' and r['messages']==[{'role':'user','content':'synthetic'}]
json.dump({'response':{'results':[{'case_id':'case1','plan_id':'P1'}]},'usage':{'output_tokens':3},'model':'STUB_V1'},sys.stdout)
'''
        with self.runner(code) as (runner, root):
            response = runner.infer('synthetic', root / 'call', batch_schema('plan_id'))
            self.assertEqual(response['results'][0]['plan_id'], 'P1')
            metadata = json.loads((root / 'call' / 'metadata.json').read_text())
            self.assertEqual(metadata['model_reported'], 'STUB_V1')
            self.assertFalse(metadata['is_model_measurement'])
            self.assertEqual(metadata['retries'], 0)

    def test_failure_is_not_retried(self):
        code = '''from pathlib import Path
import sys
p=Path(__file__).with_name('counter')
p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
print('LOCAL_DIAGNOSTIC',file=sys.stderr)
sys.exit(7)
'''
        with self.runner(code) as (runner, root):
            with self.assertRaises(RuntimeError):
                runner.infer('synthetic', root / 'call', batch_schema('plan_id'))
            self.assertEqual((root / 'counter').read_text(), '1')
            self.assertIn('LOCAL_DIAGNOSTIC', (root / 'call' / 'stderr.local.txt').read_text())
            metadata = json.loads((root / 'call' / 'metadata.json').read_text())
            self.assertEqual(metadata['return_code'], 7)
            self.assertNotIn('LOCAL_DIAGNOSTIC', json.dumps(metadata))

    def test_timeout_preserves_partial_stdout(self):
        code = "import time\nprint('PARTIAL_LOCAL_OUTPUT',flush=True)\ntime.sleep(2)\n"
        with self.runner(code, timeout=0.3) as (runner, root):
            with self.assertRaises(RuntimeError):
                runner.infer('synthetic', root / 'call', batch_schema('plan_id'))
            metadata = json.loads((root / 'call' / 'metadata.json').read_text())
            self.assertEqual(metadata['status'], 'timeout')
            self.assertIn('PARTIAL_LOCAL_OUTPUT', (root / 'call' / 'stdout.local.txt').read_text())

    def test_wrong_response_schema_is_invalid(self):
        code = "import json,sys\njson.dump({'response':{'results':[{'case_id':'case1','plan_id':7}]},'usage':{},'model':'STUB'},sys.stdout)\n"
        with self.runner(code) as (runner, root):
            with self.assertRaises(RuntimeError):
                runner.infer('synthetic', root / 'call', batch_schema('plan_id'))
            self.assertEqual(json.loads((root / 'call' / 'metadata.json').read_text())['status'], 'invalid')
            self.assertFalse((root / 'call' / 'response.json').exists())

    def test_credentials_rejected_in_params(self):
        with self.assertRaisesRegex(ValueError, 'environment'):
            with self.runner('', params={'api_key': 'DUMMY_NOT_A_REAL_KEY'}):
                pass


if __name__ == '__main__':
    unittest.main()

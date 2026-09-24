"""Small checks of selection, accounting and intervention semantics.

Tests execute only this file's synthetic fixture, never a generated controller.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import make_ablations as ab
import run_extension as run

FIXTURE = '''
calls=0
def initialize(agent_id,schema):
    global calls
    calls+=1
    return {'steps':0}
def act(local,memory):
    memory['steps']+=1
    return {'action':local.get('chosen',local['proposal']),'memory':memory}
'''


class StudyTests(unittest.TestCase):
    def write_metadata(self, root, name, value):
        directory = root / name
        directory.mkdir()
        (directory / 'metadata.json').write_text(json.dumps(value))
        return directory

    def valid_metadata(self):
        return {'status': 'completed', 'usage': [
            {'input_tokens': 100, 'output_tokens': 20,
             'cached_input_tokens': 50, 'reasoning_output_tokens': 12}]}

    def test_baseline_wins_tie_invalid_ignored(self):
        rows=[{'label':'reference','feedback':{'status':'scored','primary_score':.2}},
              {'label':'invalid','feedback':{'status':'unscored','primary_score':.9}},
              {'label':'tie','feedback':{'status':'scored','primary_score':.2}}]
        self.assertEqual(run.winner(rows)['label'],'reference')
        rows.append({'label':'better','feedback':{'status':'scored','primary_score':.21}})
        self.assertEqual(run.winner(rows)['label'],'better')

    def test_zero_is_valid_nan_cannot_win(self):
        rows=[{'feedback':{'status':'scored','primary_score':float('nan')}},
              {'label':'zero','feedback':{'status':'scored','primary_score':0}}]
        self.assertEqual(run.winner(rows)['label'],'zero')
        with self.assertRaises(ValueError):run.winner(rows[:1])

    def test_usage_does_not_double_count_subsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);call=p/'call-01';call.mkdir()
            (call/'metadata.json').write_text(json.dumps({'status':'completed','usage':[
                {'input_tokens':100,'output_tokens':20,'cached_input_tokens':50,'reasoning_output_tokens':12}]}))
            result=run.usage(p)
            self.assertEqual(result['input_plus_output_tokens'],120)
            self.assertTrue(result['usage_complete'])
            missing=p/'call-02';missing.mkdir()
            (missing/'metadata.json').write_text('{"status":"timeout"}')
            self.assertFalse(run.usage(p)['usage_complete'])

    def test_candidate_bytes_preserves_exact_bytes_and_rejects_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / 'controller.py'
            original = b'# harmless source fixture\n'
            source.write_bytes(original)
            record = {'candidate': str(directory), 'sha256': run.sha(source)}
            self.assertEqual(run.candidate_bytes(record), original)
            source.write_bytes(original + b'# changed after development\n')
            with self.assertRaises(RuntimeError):
                run.candidate_bytes(record)

    def test_candidate_bytes_rejects_file_and_directory_symlinks(self):
        for linked_directory in (False, True):
            with self.subTest(linked_directory=linked_directory), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                real = root / 'real'
                real.mkdir()
                source = real / 'controller.py'
                source.write_bytes(b'# harmless source fixture\n')
                candidate = root / 'candidate'
                if linked_directory:
                    candidate.symlink_to(real, target_is_directory=True)
                else:
                    candidate.mkdir()
                    (candidate / 'controller.py').symlink_to(source)
                with self.assertRaises(RuntimeError):
                    run.candidate_bytes({'candidate': str(candidate), 'sha256': run.sha(source)})

    def test_usage_malformed_metadata_is_incomplete_without_losing_other_calls(self):
        # A damaged call must not prevent writing a summary of known consumption.
        for malformed in ('{', 'null', '[]', '"metadata is not an object"'):
            with self.subTest(malformed=malformed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.write_metadata(root, 'call-01', self.valid_metadata())
                bad = root / 'call-02'
                bad.mkdir()
                (bad / 'metadata.json').write_text(malformed)
                result = run.usage(root, attempted=2)
                self.assertFalse(result['usage_complete'])
                self.assertEqual(result['input_plus_output_tokens'], 120)

    def test_usage_invalid_record_shapes_remain_unscored_and_keep_known_rows(self):
        shapes = (None, {}, 'bad', [None], [42], ['bad'],
                  [{'input_tokens': 7, 'output_tokens': 3}, None],
                  [{'input_tokens': 7, 'output_tokens': 3},
                   {'input_tokens': 11, 'output_tokens': 2}])
        for records in shapes:
            with self.subTest(records=records), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.write_metadata(root, 'call-01', self.valid_metadata())
                self.write_metadata(root, 'call-02', {'status': 'completed', 'usage': records})
                result = run.usage(root, attempted=2)
                self.assertFalse(result['usage_complete'])
                # Valid counters in an invalid multi-record call are still costs.
                known = sum(row.get('input_tokens', 0) + row.get('output_tokens', 0)
                            for row in records if isinstance(row, dict)) if isinstance(records, list) else 0
                self.assertEqual(result['input_plus_output_tokens'], 120 + known)

    def test_usage_negative_noninteger_and_bad_subsets_are_incomplete(self):
        mutations = (
            ('input_tokens', -1), ('output_tokens', -1),
            ('input_tokens', True), ('output_tokens', 20.0),
            ('cached_input_tokens', 101), ('cached_input_tokens', -1),
            ('cache_write_input_tokens', 101), ('cache_write_input_tokens', True),
            ('reasoning_output_tokens', 21), ('reasoning_output_tokens', -1),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                metadata = self.valid_metadata()
                metadata['usage'][0][field] = value
                self.write_metadata(root, 'call-01', metadata)
                result = run.usage(root, attempted=1)
                self.assertFalse(result['usage_complete'])
                expected = sum(n for key, n in metadata['usage'][0].items()
                               if key in ('input_tokens', 'output_tokens') and type(n) is int and n >= 0)
                self.assertEqual(result['input_plus_output_tokens'], expected)

    def test_usage_requires_exact_call_inventory_and_retains_extra_cost(self):
        for discrepancy in ('missing_directory', 'missing_metadata', 'extra_call', 'wrong_name'):
            with self.subTest(discrepancy=discrepancy), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for index in range(1, 7):
                    if index == 6 and discrepancy in ('missing_directory', 'missing_metadata', 'wrong_name'):
                        continue
                    self.write_metadata(root, f'call-{index:02d}', self.valid_metadata())
                if discrepancy == 'missing_metadata':
                    (root / 'call-06').mkdir()
                elif discrepancy == 'extra_call':
                    self.write_metadata(root, 'call-07', self.valid_metadata())
                elif discrepancy == 'wrong_name':
                    self.write_metadata(root, 'call-99', self.valid_metadata())
                result = run.usage(root, attempted=6)
                self.assertFalse(result['usage_complete'])
                expected_calls = {'missing_directory': 5, 'missing_metadata': 5,
                                  'extra_call': 7, 'wrong_name': 6}[discrepancy]
                self.assertEqual(result['input_plus_output_tokens'], 120 * expected_calls)

    def test_usage_exact_six_calls_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(1, 7):
                self.write_metadata(root, f'call-{index:02d}', self.valid_metadata())
            result = run.usage(root, attempted=6)
            self.assertTrue(result['usage_complete'])
            self.assertEqual(result['input_plus_output_tokens'], 720)
            self.assertEqual(result['known_usage']['cached_input_tokens'], 300)
            self.assertEqual(result['known_usage']['reasoning_output_tokens'], 72)

    def test_parity_checks_metrics_not_just_mean(self):
        row={'world_id':1,'score':.2,'metrics':{'x':2}}
        a={'world_ids':[1,2,3,4],'cases':[dict(row) for _ in range(4)]}
        b=json.loads(json.dumps(a));self.assertTrue(run.same_game(a,b))
        b['cases'][1]['metrics']['x']=3;self.assertFalse(run.same_game(a,b))

    def test_reset_initializes_once_and_resets_json_only(self):
        ns={};exec(ab.wrapped(FIXTURE,ab.MODES[0]),ns)
        memory=ns['initialize'](0,{'native_comm_action_ids':[2]})
        for _ in range(3):memory=ns['act']({'proposal':0},memory)['memory']
        self.assertEqual(memory,{'steps':1});self.assertEqual(ns['calls'],1)

    def test_suppress_only_added_messages_keep_memory(self):
        ns={};exec(ab.wrapped(FIXTURE,ab.MODES[1]),ns)
        memory=ns['initialize'](0,{'native_comm_action_ids':[2]})
        log=io.StringIO()
        with contextlib.redirect_stderr(log):
            first=ns['act']({'proposal':0,'chosen':2,'legal_mask':[True]*3},memory)
            second=ns['act']({'proposal':2,'chosen':2,'legal_mask':[True]*3},first['memory'])
        self.assertEqual(first['action'],0);self.assertEqual(second['action'],2)
        self.assertEqual(second['memory']['steps'],2)
        self.assertEqual(log.getvalue().strip(),ab.MARKER)

    def test_suppression_does_not_repair_illegal_action(self):
        ns={};exec(ab.wrapped(FIXTURE,ab.MODES[1]),ns)
        memory=ns['initialize'](0,{'native_comm_action_ids':[2]})
        with self.assertRaises(ValueError):
            ns['act']({'proposal':0,'chosen':2,'legal_mask':[True,True,False]},memory)

    def test_reserved_names_rejected(self):
        with self.assertRaises(ValueError):ab.wrapped(FIXTURE+'\n# '+ab.MARKER,ab.MODES[0])


if __name__=='__main__':unittest.main()

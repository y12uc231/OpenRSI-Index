"""Offline exporter tests: no inference, candidate imports, Docker or private runs.

Run with ALEM_EXPORT_REPO pointing at a checkout containing the frozen commit.
Only committed public baseline evidence is used to construct input fixtures.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).with_name('export_alem_researcher.py')
spec = importlib.util.spec_from_file_location('exporter', FILE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)
REPO = Path(os.environ.get('ALEM_EXPORT_REPO', '.')).resolve()


def source_map(frozen):
    names={'TASK_DESIGN.md', 'pilot/PROTOCOL.md', 'pilot/run.py', 'controller/engine.py', 'controller/launcher.py', 'controller/controller_driver.py', 'controller/wire.py', 'controller/feedback.py', 'controller/CONTRACT.md', 'baseline/source-manifest.json', 'baseline/asset-manifest.json', '../relayrepair/pilot/codex_runner.py', '../livemigrate/pilot/compatible_adapter.py', '../livemigrate/compute/qwen38.json'}
    return {n:e.sha(frozen.raw('contributor-work/'+n[3:] if n.startswith('../') else e.TASK+'/'+n)) for n in names}


def fixture(frozen, suite='evaluation'):
    public=frozen.obj(e.TASK+'/controller/evidence/'+('dev' if suite=='dev' else 'evaluation')+'-baseline.json')
    source=frozen.obj(e.TASK+'/baseline/source-manifest.json');assets=frozen.obj(e.TASK+'/baseline/asset-manifest.json')
    return {'suite':suite,'status':'scored','provenance_verified':True,'infrastructure_affected':False,'primary_score':public['primary_score_fraction'],'world_ids':public['world_ids'],'total':public['total'],'scored':public['scored'],'metrics_mean':public['reward_fraction_mean'],
            'cases':[{'world_id':r['world_id'],'status':r['status'],'naturally_terminated':r['naturally_terminated'],'metrics':r['reward_fraction'],'trace_sha256':r['trace_sha256'],**r['costs']} for r in public['worlds']],
            'host_provenance':{'source_candidate_unchanged':True,'environment_image':public['environment_image'],'worker_image':public['worker_image'],'wall_seconds':public['host_wall_seconds'],'operator_timeout_seconds':public['operator_timeout_seconds'],'hashes':{'candidate_sha256':public['candidate_sha256'],'source_revision':source['revision'],'source_sha256':source['files'],'asset_revision':assets['revision'],'asset_sha256':{r['path'].removeprefix('assets/'):r['sha256'] for r in assets['files']},'runner_sha256':public['runner_sha256'],'manifest_sha256':{k:e.sha(frozen.raw(e.TASK+'/baseline/'+k)) for k in ('source-manifest.json','asset-manifest.json')}}}}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.frozen = e.Frozen(REPO)
        self.value = fixture(self.frozen)
        self.hash = self.value['host_provenance']['hashes']['candidate_sha256']
    def test_public_baseline_recomputes_exactly(self):
        x, f = e.sanitize_result(self.value, 'evaluation', self.hash, self.frozen)
        self.assertEqual(x['status'], 'scored')
        self.assertAlmostEqual(x['primary_score_fraction'], .18522013239562513)
        self.assertEqual(len(x['worlds']), 20)
        self.assertFalse(x['audit_problems'])
    def test_candidate_hash_mismatch_is_unscored(self):
        x, f = e.sanitize_result(self.value, 'evaluation', '0'*64, self.frozen)
        self.assertIsNone(x['primary_score_fraction'])
        self.assertIn('candidate_hash_mismatch', x['audit_problems'])
    def test_dropped_world_is_unscored(self):
        self.value['cases'].pop()
        x, f = e.sanitize_result(self.value, 'evaluation', self.hash, self.frozen)
        self.assertIsNone(x['primary_score_fraction'])
        self.assertEqual(len(x['worlds']), 19)
        self.assertIn('world_inventory_mismatch', x['audit_problems'])
    def test_forged_score_is_unscored(self):
        self.value['primary_score'] = 1
        x, f = e.sanitize_result(self.value, 'evaluation', self.hash, self.frozen)
        self.assertIsNone(x['primary_score_fraction'])
        self.assertIn('score_aggregation_mismatch', x['audit_problems'])
    def test_infra_retains_all_worlds_without_score(self):
        self.value['provenance_verified'] = False
        self.value['infrastructure_affected'] = True
        x, f = e.sanitize_result(self.value, 'evaluation', self.hash, self.frozen)
        self.assertEqual(len(x['worlds']), 20)
        self.assertIsNone(x['primary_score_fraction'])
    def test_private_fields_not_exported(self):
        self.value['reasoning'] = 'PRIVATE REASONING SENTINEL'
        self.value['host_provenance']['commands'] = ['/Users/secret/shell']
        self.value['cases'][0]['error'] = '/Users/private/abc'
        x, f = e.sanitize_result(self.value, 'evaluation', self.hash, self.frozen)
        self.assertNotIn('PRIVATE', json.dumps(x))
        self.assertNotIn('/Users/', json.dumps(x))
    def test_wrong_image_unscored(self):
        self.value['host_provenance']['environment_image'] = 'sha256:'+'0'*64
        x, f = e.sanitize_result(self.value, 'evaluation', self.hash, self.frozen)
        self.assertIn('container_image_mismatch', x['audit_problems'])
        self.assertIsNone(x['primary_score_fraction'])
    def test_metadata_filters_fields_and_unknown_usage(self):
        x = e.metadata({'status':'completed','reasoning_effort':'ultra','tool_free':True,'return_code':0,'model_requested':'gpt-6-sol','usage':[{'input_tokens':1,'output_tokens':2,'secret':'/Users/private'}],'reasoning':'hidden'}, 'gpt-6-sol')
        self.assertTrue(x['complete_call_evidence'])
        self.assertNotIn('hidden', json.dumps(x))
        self.assertNotIn('/Users', json.dumps(x))
        self.assertFalse(e.metadata({'status':'completed','usage':[{'input_tokens':-1,'output_tokens':2}]},'gpt-6-sol')['complete_call_evidence'])
    def test_full_export_preserves_every_generation_without_private_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'run'; root.mkdir(); out=Path(tmp)/'export'
            (root/'source-sha256.json').write_bytes(e.json_bytes(source_map(self.frozen)))
            study=self.frozen.obj(e.TASK+'/pilot/STUDY.json')
            (root/'packet-manifest.json').write_bytes(e.json_bytes(study['public_packet_files']))
            candidate=self.frozen.raw(e.TASK+'/controller/reference/controller.py')
            for i in range(3):
                call=root/f'call-{i:02d}';call.mkdir()
                (call/'response.json').write_bytes(e.json_bytes({'controller':candidate.decode(), 'note':'private implementation note excluded'}))
                (call/'metadata.json').write_bytes(e.json_bytes({'status':'completed','reasoning_effort':'ultra','model_requested':'gpt-6-astra','tool_free':True,'return_code':0,'seconds':1,'usage':[{'input_tokens':100,'output_tokens':10,'cached_input_tokens':20}]}))
                (call/'events.jsonl').write_text('PRIVATE REASONING SENTINEL /Users/private')
                cand=root/f'candidate-{i:02d}';cand.mkdir();(cand/'controller.py').write_bytes(candidate)
                check=root/f'check-{i:02d}';check.mkdir()
                (check/'result.json').write_bytes(e.json_bytes(fixture(self.frozen,'evaluation' if i==2 else 'dev')))
                (check/'operator.json').write_bytes(e.json_bytes({'return_code':0,'queue_seconds':0,'seconds':1,'private':'/Users/private'}))
            summary={'model_requested':'gpt-6-astra','status':'completed','source_git_commit':e.COMMIT,'source_unchanged':True,'matched_baseline_sha256':study['matched_baseline_result_sha256'],'matched_baseline_primary_score':study['matched_baseline_score'],'final_candidate_sha256':e.sha(candidate),'final_evaluation':{'primary_score':study['matched_baseline_score']},'known_usage':{'input_tokens':300,'output_tokens':30,'cached_input_tokens':60},'usage_complete':True,'calls_attempted':3,'calls_completed':3,'seconds':5}
            (root/'summary.json').write_bytes(e.json_bytes(summary))
            exported=e.export(root, REPO, out)
            self.assertEqual(exported['audit_status'], 'verified')
            self.assertEqual(exported['primary_score_fraction'], study['matched_baseline_score'])
            self.assertEqual(exported['total_input_plus_output_tokens'],330)
            self.assertEqual(len(json.loads((out/'final-evaluation.json').read_text())['worlds']),20)
            for i in range(3): self.assertEqual((out/f'generation-{i+1:02d}/controller.py').read_bytes(), candidate)
            for p in out.rglob('*'):
                if p.is_file():
                    self.assertNotIn('PRIVATE REASONING',p.read_text())
                    self.assertNotIn('/Users/',p.read_text())
                    self.assertNotIn('private implementation note',p.read_text())
            with self.assertRaises(ValueError): e.export(root, REPO, out)
            summary['status']='unscored_infrastructure_or_invalid_response'
            summary.pop('final_candidate_sha256')
            (root/'summary.json').write_bytes(e.json_bytes(summary))
            (root/'call-02/response.json').write_bytes(e.json_bytes({'note':'not a valid source'}))
            incomplete=e.export(root, REPO, Path(tmp)/'incomplete')
            self.assertEqual(incomplete['audit_status'],'needs_review')
            self.assertIn('missing_generation_artifact',incomplete['audit_problems'])
            self.assertIn('incomplete_researcher_run',incomplete['audit_problems'])
            self.assertIsNone(incomplete['primary_score_fraction'])
    def test_reader_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'target').write_text('x');(root/'x').symlink_to(root/'target')
            with self.assertRaises(ValueError): e.Reader(root).raw('x')
    def test_source_inventory_matches_frozen_pilot(self):
        self.assertTrue(self.frozen.source_map(source_map(self.frozen)))

if __name__ == '__main__': unittest.main()

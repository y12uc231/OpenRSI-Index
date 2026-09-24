"""Safe exporter for the preregistered author-written visible-sync control."""
import argparse
import json
from pathlib import Path
import export_alem_researcher as e

def export(run, repo, output):
    if output.exists(): raise ValueError('Refusing existing output')
    reader, frozen = e.Reader(run), e.Frozen(repo)
    raw = frozen.raw(e.TASK + '/controls/visible_sync/controller.py')
    value, feedback = e.sanitize_result(reader.obj('result.json'), 'evaluation', e.sha(raw), frozen)
    operator = reader.obj('operator.json')
    if operator.get('return_code') != 0 or operator.get('source_git_commit') != e.COMMIT:
        raise ValueError('Control operator provenance mismatch')
    if value['audit_problems']: raise ValueError('Control audit failed: ' + str(value['audit_problems']))
    value['source_result_sha256'] = reader.reads['result.json']
    baseline = frozen.obj(e.TASK + '/controller/evidence/evaluation-baseline.json')
    score = value['primary_score_fraction']
    summary = {'scope': 'one preregistered author-written scripted comparison; no model calls or tuning',
               'source_git_commit': e.COMMIT, 'controller_sha256': e.sha(raw), 'aggregate_feedback': feedback,
               'matched_baseline_primary_score_fraction': baseline['primary_score_fraction'],
               'coordination_gain_fraction': score - baseline['primary_score_fraction'] if score is not None else None,
               'operator': {k: e.number(operator.get(k)) for k in ('return_code', 'queue_seconds', 'seconds')},
               'limitations': ['Author-written heuristic, not model research evidence', 'One rollout on public canonical worlds', 'Natural termination is not success and reward fractions are not pass rates']}
    files = {'controller.py':raw,'final-evaluation.json':e.json_bytes(value),'summary.json':e.json_bytes(summary)}
    if any(e.PRIVATE.search(raw.decode()) for raw in files.values()): raise ValueError('Sensitive pattern')
    reader.verify()
    files['MANIFEST.json'] = e.json_bytes({k:e.sha(v) for k,v in files.items()})
    output.mkdir(parents=True)
    for name,raw in files.items(): (output/name).write_bytes(raw)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    x=export(a.run.resolve(),a.repo.resolve(),a.output.resolve())
    print(json.dumps({'primary_score_fraction':x['aggregate_feedback']['primary_score'],'coordination_gain_fraction':x['coordination_gain_fraction']},indent=2))

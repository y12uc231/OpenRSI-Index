"""Compare allowlisted exports, retaining all arms and every world."""
import argparse
import json
from pathlib import Path
import statistics
import export_alem_researcher as e

def compare(public, repo):
    frozen=e.Frozen(repo)
    baseline=frozen.obj(e.TASK+'/controller/evidence/evaluation-baseline.json')
    dev=frozen.obj(e.TASK+'/controller/evidence/dev-baseline.json')
    rows=[{'arm':'matched_pass_through','source':'trusted frozen policy','development_primary_score_fraction':dev['primary_score_fraction'],'final_primary_score_fraction':baseline['primary_score_fraction'],'final_worlds':baseline['scored'],'final_worlds_expected':baseline['total'],'host_wall_seconds':baseline['host_wall_seconds'],'coordination_gain_fraction':0,'generations':[]}]
    world_table={r['world_id']:{'world_id':r['world_id'],'matched_pass_through':r['reward_fraction'][e.PRIMARY]} for r in baseline['worlds']}
    for name in ['visible-sync-001','astra-001','sol-001']:
        d=public/name
        if not (d/'summary.json').is_file(): raise ValueError('All declared arms must finish before comparison: '+name)
        summary=json.loads((d/'summary.json').read_text())
        result=json.loads((d/'final-evaluation.json').read_text()) if (d/'final-evaluation.json').is_file() else {}
        score=result.get('primary_score_fraction')
        if name!='visible-sync-001' and summary.get('primary_score_fraction') is None:score=None
        row={'arm':name,'source':'author-written heuristic' if name=='visible-sync-001' else 'one three-call tool-free researcher attempt','final_primary_score_fraction':score,'coordination_gain_fraction':score-baseline['primary_score_fraction'] if score is not None else None,'final_worlds':result.get('scored',0),'final_worlds_expected':20,'host_wall_seconds':result.get('host_wall_seconds'),'reward_fraction_mean':result.get('reward_fraction_mean',{}),'aggregate_costs':result.get('aggregate_costs',{}),'native_diagnostics_mean':result.get('native_diagnostics_mean',{}),'generations':[{'generation':g['generation'],'artifact_available':g['artifact_available'],'controller_sha256':g.get('controller_sha256'),'status':g.get('aggregate_feedback',{}).get('status','not_evaluated'),'primary_score_fraction':g.get('aggregate_feedback',{}).get('primary_score'),'scored':g.get('aggregate_feedback',{}).get('scored',0),'total':g.get('aggregate_feedback',{}).get('total',20 if g['generation']==3 else 4),'inference':g.get('inference',{})} for g in summary.get('generations',[])], 'known_usage':summary.get('known_usage',{}),'usage_complete_and_consistent':summary.get('usage_complete_and_consistent')}
        deltas=[]
        for case in result.get('worlds',[]):
            wid=case['world_id']
            if wid not in world_table:raise ValueError('Unexpected world')
            v=case.get('reward_fraction',{}).get(e.PRIMARY) if case.get('status')=='scored' else None
            world_table[wid][name]=v
            if v is not None:deltas.append(v-world_table[wid]['matched_pass_through'])
        if score is not None and len(deltas)==20:
            row['paired_world_differences']={'mean_fraction':statistics.mean(deltas),'sample_sd_fraction':statistics.stdev(deltas),'min_fraction':min(deltas),'max_fraction':max(deltas),'better_worlds':sum(d>1e-12 for d in deltas),'equal_worlds':sum(abs(d)<=1e-12 for d in deltas),'worse_worlds':sum(d< -1e-12 for d in deltas)}
        rows.append(row)
    return {'schema_version':1,'frozen_source_git_commit':e.COMMIT,'score_unit':'native normalized reward fraction, not a pass rate','arms':rows,'all_world_scores':[world_table[k] for k in sorted(world_table)],'limitations':['The scripted control is nearly inactive (9 action overrides); its weakness cannot establish task difficulty','One attempt per provider alias and three calls are not a general model capability study','No inference/training is used within game actors; they are frozen MARL policies with generated Python controllers','Public canonical worlds are not secret heldout data','Survival and synchronization both affect returns; category metrics do not establish causal mechanisms','No confidence claim or model population inference is made from these paired fixed worlds']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--public',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Refusing overwrite')
    x=compare(a.public,a.repo);a.output.write_bytes(e.json_bytes(x))

"""Run an isolated two-worker CooperBench pilot; public checks and final Judge are distinct."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parent/'relayrepair'/'pilot'))
from policies import Policy, BudgetLedger, BudgetExceeded, TelemetryError
from codex_runner import infer as codex_infer
from runner.worker import Worker, PrivateContainer, ACTION_SCHEMA


def footprint(patch):
    paths=re.findall(r'^diff --git a/(\S+) b/\S+$',patch,re.M)
    additions='\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
    exports=re.findall(r'^\s*(?:async\s+)?(?:def|class)\s+(\w+)',additions,re.M)
    imports=re.findall(r'\b(?:from\s+[\w.]+\s+import|import)\s+(\w+)',additions)
    return {'changed_paths':sorted(set(paths)),'exports':sorted(set(exports)),'imports':sorted(set(imports))}


def checked_asset(source,descriptor):
    p=(source/descriptor['path']).resolve()
    if source.resolve() not in p.parents: raise ValueError('Asset leaves source checkout')
    data=p.read_bytes()
    if hashlib.sha256(data).hexdigest()!=descriptor['sha256']: raise ValueError('Pinned source asset changed')
    return data.decode()


def evaluator_budget_exhausted(result):
    """Public evaluator deadlines may be reported by either nested stage."""
    stages = [result, result.get('merge'), result.get('public_check')]
    return any(isinstance(stage, dict) and stage.get('budget_exhausted') is True
               for stage in stages)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--task',required=True)
    parser.add_argument('--policy',choices=['periodic','always_verify','adaptive'],default='periodic')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-calls',type=int,default=32)
    parser.add_argument('--max-checks',type=int,default=4)
    parser.add_argument('--max-tool-seconds',type=float,default=900)
    parser.add_argument('--max-episode-seconds',type=float,default=3600)
    parser.add_argument('--mock',action='store_true',help='Controller wiring test only; no model inference or performance claim')
    args=parser.parse_args()
    if args.max_calls<1 or args.max_checks<0: parser.error('Invalid pilot budget')
    output=args.output.resolve()
    if ROOT.parents[1] in output.parents: parser.error('Raw runs must be outside the contribution checkout')
    output.mkdir(parents=True,exist_ok=False)
    manifest_path=ROOT/'manifests'/'pilot-v1.json'
    manifest=json.loads(manifest_path.read_text())
    case=next(c for c in manifest['cases'] if c['task_id']==args.task)
    config_path=ROOT/'policies'/'configs'/(args.policy+'.json')
    config=json.loads(config_path.read_text())
    policy=Policy(config)
    ledger=BudgetLedger(max_calls=args.max_calls,max_checks=args.max_checks,max_tool_seconds=args.max_tool_seconds)
    run_config={'started_utc':datetime.now(timezone.utc).isoformat(),'task':args.task,'policy':config,
                'max_calls':args.max_calls,'max_checks':args.max_checks,'max_tool_seconds':args.max_tool_seconds,
                'max_episode_seconds':args.max_episode_seconds,
                'inference':'MOCK_NOT_MODEL' if args.mock else 'local Codex CLI gpt-6-astra ultra; tool-free JSON action proxy',
                'budget_lane':'call_count_and_tool_wall_time; not a matched-token study',
                'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                'policy_config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),
                'inference_adapter_sha256':hashlib.sha256((ROOT.parent/'relayrepair'/'pilot'/'codex_runner.py').read_bytes()).hexdigest(),
                'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(ROOT.rglob('*.py')) if '__pycache__' not in p.parts}}
    (output/'run_config.json').write_text(json.dumps(run_config,indent=2)+'\n')
    events=[]
    def log(event):
        events.append(event)
        with (output/'events.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
    def save_budget():
        (output/'budget.json').write_text(json.dumps(ledger.summary(),indent=2)+'\n')
    containers=[]; workers=[]; started=time.monotonic()
    verified_hash=None; last_pass=None; feedback=''; turns_since=0; last_worker=None
    status={'status':'running','task':args.task,'measurement_type':'MOCK_NOT_MODEL' if args.mock else 'ONE_MODEL_FEASIBILITY_PILOT'}
    evaluator=None
    try:
        specs=[checked_asset(args.source,case['feature_specs'][str(feature)]) for feature in case['features']]
        for i,role in enumerate(['lead','member']):
            container=PrivateContainer(case['image'],role)
            containers.append(container)
            if container.original_base!=case['base_commit']:raise RuntimeError('Worker image original base mismatch')
            feature=specs[i]
            if role=='lead':
                feature+='\n\nTEAM LEAD RESPONSIBILITY: after your own feature is implemented, inspect your teammate\'s patch, resolve integration conflicts, and ensure the resulting source supports both features. If patches cannot merge, the grader uses your lead patch. Do not assume a message means code is complete.\nTEAMMATE FEATURE:\n'+specs[1]
            feature+='\n\nEDIT BOUNDARY: change runtime source under '+', '.join(case['source_prefixes'])+'. You may add or change public tests under tests/ for your own checks; the final Judge restores original tests and supplies its own. Do not change packaging, build configuration, dependencies, or runner files.'
            workers.append(Worker(role,feature,container))
        # Import trusted evaluator after setup, keeping its paths out of model prompts.
        from evaluator.checker import evaluate
        evaluator=evaluate
        steps=0
        while True:
            steps+=1
            if steps>args.max_calls+args.max_checks+5:raise RuntimeError('Controller scheduling failed to make progress')
            if time.monotonic()-started>=args.max_episode_seconds:
                status['episode_time_limit_reached']=True
                break
            if ledger.tool_seconds>=args.max_tool_seconds:
                status['tool_time_limit_reached']=True
                break
            patches={w.worker_id:w.latest_patch for w in workers}
            nonempty=any(patches.values())
            candidate_hash=hashlib.sha256(json.dumps(patches,sort_keys=True).encode()).hexdigest() if nonempty else None
            budget=ledger.summary()
            state={'workers':[{'id':w.worker_id,'turns':w.turns,'done':w.done,'revision':w.revision,
                               **footprint(w.latest_patch)} for w in workers],
                   'candidate_hash':candidate_hash,'verified_hash':verified_hash,'last_verify_passed':last_pass,
                   'turns_since_verify':turns_since,'last_worker_id':last_worker,'verification_feedback':feedback,
                   'worker_calls_remaining':max(0,args.max_calls-budget['calls_started']),
                   'checks_remaining':max(0,args.max_checks-budget['public_checks_started'])}
            decision=policy.action(state)
            log({'kind':'policy','state':state,'decision':decision})
            if decision['action']=='finish':break
            if decision['action']=='joint_verify':
                remaining_tool=args.max_tool_seconds-ledger.tool_seconds
                remaining_episode=args.max_episode_seconds-(time.monotonic()-started)
                if remaining_tool<=5:
                    status['tool_time_limit_reached']=True
                    break
                if remaining_episode<=5:
                    status['episode_time_limit_reached']=True
                    break
                limiting_budget='episode' if remaining_episode<remaining_tool else 'tool'
                ticket=ledger.start_tool(is_check=True)
                begin=time.monotonic()
                result=evaluate(args.task,patches,mode='public',source_root=args.source,
                                output_path=output/f'public-check-{budget["public_checks_started"]+1:02d}.json',
                                max_seconds=min(remaining_tool,remaining_episode)-5)
                ledger.finish_tool(ticket,time.monotonic()-begin)
                if evaluator_budget_exhausted(result):
                    status[limiting_budget+'_time_limit_reached']=True
                    status['work_stop']='budget_exhausted'
                    break
                if not result.get('validinfra',False):raise RuntimeError('Public checker infrastructure failure; inspect preserved result')
                verified_hash=candidate_hash
                last_pass=result.get('public_passed',False)
                feedback=json.dumps({k:v for k,v in result.items() if k not in {'merged_patch'}})[-16000:]
                for w in workers:
                    w.history.append({'kind':'public_check','candidate_revision':verified_hash,'passed':last_pass,'feedback':feedback})
                    if not last_pass:w.done=False
                turns_since=0
                log({'kind':'public_check','passed':last_pass,'candidate_revision':verified_hash})
                print(f'{args.task} {args.policy}: public check={last_pass}',flush=True)
                save_budget();continue
            w=next(w for w in workers if w.worker_id==decision['worker_id'])
            peer=next(peer for peer in workers if peer is not w)
            w.container.write('/tmp/jointverify-peer.patch',peer.latest_patch)
            if decision['message_context']:
                w.history.append({'kind':'policy_context','items':decision['message_context']})
            prompt=w.prompt(peer.revision,state['worker_calls_remaining'])
            call_ticket=ledger.reserve_call()
            call_dir=output/f'call-{call_ticket+1:02d}-{w.worker_id}'
            if args.mock:
                call_dir.mkdir()
                response={'action':'finish','command':'','message':'Deterministic wiring stub; no feature implemented.','summary':'MOCK_NOT_MODEL'}
                (call_dir/'prompt.txt').write_text(prompt)
                (call_dir/'response.json').write_text(json.dumps(response))
                (call_dir/'metadata.json').write_text(json.dumps({'usage':[{'input_tokens':0,'output_tokens':0}],
                    'measurement_type':'MOCK_NOT_MODEL'}))
            else:
                response=codex_infer(prompt,call_dir,ACTION_SCHEMA,timeout=min(480,max(1,int(args.max_episode_seconds-(time.monotonic()-started)))))
            metadata=json.loads((call_dir/'metadata.json').read_text())
            if len(metadata['usage'])!=1:raise TelemetryError('Expected one completed call usage record')
            ledger.settle_call(call_ticket,metadata['usage'][0])
            remaining_tool=max(0,args.max_tool_seconds-ledger.tool_seconds)
            remaining_episode=args.max_episode_seconds-(time.monotonic()-started)
            if remaining_episode<=0:
                status['episode_time_limit_reached']=True
                break
            if response.get('action')=='shell' and min(remaining_tool,remaining_episode)<=5:
                status['tool_time_limit_reached' if remaining_tool<=remaining_episode else 'episode_time_limit_reached']=True
                break
            tool_ticket=ledger.start_tool() if response.get('action')=='shell' else None
            w.container.command_seconds=max(0.1,min(90,remaining_tool-5,remaining_episode-5))
            accept_started=time.monotonic()
            old_revision=w.revision
            try:
                observation=w.accept(response)
            except (ValueError,RuntimeError) as exc:
                # Preserve the latest successfully harvested patches. Worker
                # protocol/repository damage terminates work, never drops a case.
                status['worker_failure']={'worker':w.worker_id,'error':str(exc)}
                log({'kind':'worker_failure',**status['worker_failure']})
                if tool_ticket is not None:
                    ledger.finish_tool(tool_ticket,time.monotonic()-accept_started)
                break
            if tool_ticket is not None:ledger.finish_tool(tool_ticket,observation['wall_seconds'])
            if response['message']:
                peer.history.append({'kind':'message','sender':w.worker_id,'revision':w.revision,'text':response['message']})
            if w.done:
                peer.history.append({'kind':'peer_status','sender':w.worker_id,'status':'finished','revision':w.revision})
            if peer.worker_id=='lead' and peer.done and w.latest_patch and w.revision!=old_revision:
                peer.done=False
                peer.history.append({'kind':'integration_notice','text':'Your member changed its patch after your last completion. Inspect the new snapshot and confirm joint integration before finishing.'})
            (output/f'{w.worker_id}.patch').write_text(w.latest_patch)
            turns_since+=1;last_worker=w.worker_id
            log({'kind':'worker','worker':w.worker_id,'turn':w.turns,'action':response['action'],
                 'revision':w.revision,'patch_bytes':len(w.latest_patch),'usage':metadata['usage'][0]})
            print(f'{args.task} {args.policy}: call {call_ticket+1} {w.worker_id} {response["action"]}; patch {len(w.latest_patch)} bytes',flush=True)
            save_budget()
    except BudgetExceeded as exc:
        status.update(work_stop='budget_exhausted',budget_error=str(exc))
    except Exception as exc:
        status.update(status='incomplete',error_type=type(exc).__name__,error=str(exc),
                      elapsed_seconds=round(time.monotonic()-started,3))
    finally:
        # Judge grading is independent of worker/public-check budgets. Preserve
        # diagnostic grading even after a worker or infrastructure interruption.
        if evaluator is not None and len(workers)==2:
            try:
                patches={w.worker_id:w.latest_patch for w in workers}
                judged=evaluator(args.task,patches,mode='judge',source_root=args.source,
                                 output_path=output/'judge-details.json')
                (output/'judge-result.json').write_text(json.dumps(judged,indent=2)+'\n')
                status['result']=judged
                if status['status']!='incomplete':
                    status['status']='completed' if judged.get('validinfra',False) else 'infrastructure_failure'
                if ledger.overrun or status.get('tool_time_measurement_incomplete'):
                    status['status']='unscored_budget_or_telemetry_failure'
            except Exception as exc:
                status.update(status='infrastructure_failure',judge_error=str(exc))
        status['elapsed_seconds']=round(time.monotonic()-started,3)
        save_budget()
        (output/'status.json').write_text(json.dumps(status,indent=2)+'\n')
        for container in containers:container.close()
    print(json.dumps({'task':args.task,'status':status['status'],'measurement_type':status['measurement_type'],
                      'both_features_passed':status.get('result',{}).get('both_features_passed'),
                      'elapsed_seconds':status.get('elapsed_seconds'),'budget':ledger.summary()},indent=2),flush=True)

if __name__=='__main__':main()

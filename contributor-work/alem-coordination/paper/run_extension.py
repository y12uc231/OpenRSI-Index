"""Six-call Sol continuation. Generated code runs only inside the audited evaluator."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
TRANSPORT = TASK.parent / 'relayrepair/pilot/codex_runner.py'
SOL_SHA = '3862d57dbf57dbb8e1f2efff6cd32a345dd7006a0dab58d40b45e0ff5ae38d89'
PACKET_SHA = 'd64f2fe9425d12ae34f3e00c1ca0743e7a60569102b687195bc6c9b6a912bea3'
PARITY_SHAS = ('f63346bf8e87b6bcc1d2330658eed55427b5fcd1a12f54f2b46b9763ff9560f2',
               '1db38ea3608ba8cac70d034b469e8caeaa99fa5ddad4ded2683430f50b8f1e6a')
MAX_CANDIDATE = 1024 * 1024
CALLS = 6
SCHEMA = {'type': 'object', 'properties': {'controller': {'type': 'string'},
          'note': {'type': 'string'}}, 'required': ['controller', 'note'],
          'additionalProperties': False}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    exec(compile(Path(path).read_bytes(), str(path), 'exec'), value.__dict__)
    return value


def winner(records):
    """Stable argmax: a valid zero is eligible; invalid outcomes never win."""
    selected = None
    for row in records:
        score = row['feedback'].get('primary_score')
        if row['feedback'].get('status') != 'scored' or type(score) not in (int, float):
            continue
        if not 0 <= score <= 1:
            continue
        if selected is None or score > selected['feedback']['primary_score']:
            selected = row
    if selected is None:
        raise ValueError('No valid development candidate')
    return selected


def usage(output, attempted=None):
    total = {}; calls = []; complete = True
    for path in sorted(output.glob('call-*/metadata.json')):
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError):
            value = {}
        if not isinstance(value,dict):value={}
        records = value.get('usage', [])
        if not isinstance(records,list):records=[]
        valid = (value.get('status') == 'completed' and len(records) == 1 and
                 isinstance(records[0],dict) and
                 all(type(records[0].get(k)) is int and records[0][k] >= 0
                     for k in ('input_tokens','output_tokens')))
        if valid:
            r=records[0]
            for subset,parent in [('cached_input_tokens','input_tokens'),
                    ('cache_write_input_tokens','input_tokens'),('reasoning_output_tokens','output_tokens')]:
                if subset in r and (type(r[subset]) is not int or not 0 <= r[subset] <= r[parent]):
                    valid=False
        complete = complete and valid
        for row in records:
            if not isinstance(row,dict):continue
            for key, number in row.items():
                if type(number) is int and number >= 0:
                    total[key] = total.get(key, 0) + number
        calls.append({'call': path.parent.name, 'status': value.get('status'),
                      'seconds': value.get('seconds'), 'usage': records})
    if attempted is not None:
        entries={p.name for p in output.glob('call-*')}
        expected={f'call-{i:02d}' for i in range(1,attempted+1)}
        complete=complete and entries==expected and len(calls)==attempted
    return {'known_usage': total, 'calls': calls, 'usage_complete': complete,
            'input_plus_output_tokens': total.get('input_tokens',0) + total.get('output_tokens',0),
            'cached_input_and_reasoning_output_are_subsets': True}


def candidate_bytes(record):
    path=Path(record['candidate'])/'controller.py'
    data=path.read_bytes()
    if path.parent.is_symlink() or path.is_symlink() or hashlib.sha256(data).hexdigest()!=record['sha256']:
        raise RuntimeError('Candidate differs from its development record')
    return data


def same_game(old, new):
    fields = ('world_id','status','steps','naturally_terminated','score','metrics',
              'overrides','action_count','native_communication_actions','trace_sha256')
    return (old.get('world_ids') == new.get('world_ids') and
            len(old.get('cases',[])) == len(new.get('cases',[])) == 4 and
            all(all(a.get(k) == b.get(k) for k in fields)
                for a,b in zip(old['cases'],new['cases'])))


def prompt(packet, latest_code, best_code, history, index):
    return (
      'This is a six-call continuation study of Alem controller development. '
      'You are the researcher, not a game actor. Return complete Python standard-library '
      'controller.py source and a brief implementation note. No direct tools are available. '
      'Improve mean coordination reward while following the original local-observation '
      'and legal-action contract. You may retain or replace the starting controller. '
      'Do not hard-code worlds, change the environment, inspect hidden state, use a '
      'simulator oracle, external services, clocks or system entropy. Any legal action '
      'is allowed; the trained policy still advances on each real observation. '
      'Your code runs in three private processes. Native communication consumes a turn. '
      'The runtime has only one writable private scratch file /tmp/scratch, at most 16 MiB; '
      'no general temporary-file creation. JSON memory is at most 65536 bytes. '
      'The UTF-8 controller source must be at most 1 MiB. '
      'The old task design describes the original experiment. This continuation changes '
      'only the research-call budget and later final test: all six submissions receive '
      'feedback on the same four development worlds. No final-world feedback returns. '
      'The submitted final file will be selected by highest valid development reward '
      'among pass-through, the original Sol controller and all six submissions; '
      'exact ties keep the earliest in that order. Invalid submissions remain recorded. '
      'Treat final testing as separate; do not regenerate or target evaluation maps. '
      f'This is new call {index}/{CALLS}.\n' + packet +
      '\nLATEST CONTROLLER:\n' + latest_code +
      '\nBEST DEVELOPMENT CONTROLLER SO FAR:\n' + best_code +
      '\nAGGREGATE DEVELOPMENT HISTORY:\n' + json.dumps(history, allow_nan=False)
    )


def execute(args):
    args.output.mkdir(parents=True, exist_ok=False)
    initial = TASK/'results/sol-001/generation-03/controller.py'
    if sha(initial) != SOL_SHA or sha(args.packet/'MANIFEST.json') != PACKET_SHA:
        raise RuntimeError('Starting controller or original packet identity changed')
    for path,expected in zip((args.old_reference_dev,args.old_sol_dev),PARITY_SHAS):
        if sha(path)!=expected:raise RuntimeError('Expected development input changed')
    backend = module('alem_continuation_transport', TRANSPORT)
    backend.MODEL, backend.EFFORT = 'gpt-6-sol', 'ultra'
    pilot = module('alem_continuation_packet', TASK/'pilot/run.py')
    evaluator = module('alem_continuation_evaluator', HERE/'run_evaluation.py')
    feedback = module('alem_continuation_feedback', TASK/'controller/feedback.py').public_feedback
    packet, packet_manifest = pilot.public_packet(args.packet)
    tracked = [HERE/'EXTENSION-PROTOCOL.md', HERE/'run_extension.py', HERE/'run_evaluation.py',
               HERE/'make_ablations.py', TRANSPORT, TASK/'pilot/run.py',
               TASK/'baseline/common.py', TASK/'TASK_DESIGN.md',
               TASK/'controller/reference/controller.py', initial,
               args.old_reference_dev,args.old_sol_dev,args.packet/'MANIFEST.json',
               TASK/'baseline/source-manifest.json', TASK/'baseline/asset-manifest.json']
    tracked += sorted((TASK/'native').glob('*.py'))
    tracked += [TASK/'native/README.md',TASK/'native/ENGINE.patch']
    tracked += [TASK/'controller'/n for n in ['launcher.py','engine.py','wire.py','feedback.py',
                                           'controller_driver.py','CONTRACT.md']]
    tracked += [args.packet/name for name in packet_manifest]
    identities = {str(p):sha(p) for p in tracked}
    def unchanged():
        return all(p.is_file() and not p.is_symlink() and sha(p)==identities[str(p)] for p in tracked)
    dump(args.output/'study-inputs.json', {'files':identities,'packet_manifest':packet_manifest,
        'starting_sol_sha256':SOL_SHA,'source_commit':subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=TASK,text=True).strip(),'protocol_sha256':sha(HERE/'EXTENSION-PROTOCOL.md'),
        'declared_calls':CALLS,'model_requested':'gpt-6-sol','reasoning_effort':'ultra',
        'fresh_worlds':list(range(30000,30020)), 'original_worlds':list(range(9999,10019))})
    records=[]; history=[]; final=[]
    status={'status':'running','phase':'initial_development_parity','calls_attempted':0,
            'declared_calls':CALLS,'selection_rule':'max_valid_development_earliest_tie',
            'started_at_unix':time.time(),'model_requested':'gpt-6-sol','records':records,'final':final}
    started=time.monotonic()
    def save():
        status['elapsed_seconds']=time.monotonic()-started
        status['usage']=usage(args.output,status['calls_attempted'])
        status['usage']['usage_complete'] = (status['usage']['usage_complete'] and
                  len(status['usage']['calls']) == status['calls_attempted'])
        dump(args.output/'summary.private.json',status)
    def evaluate(label, candidate, suite):
        if not unchanged():raise RuntimeError('Study input changed')
        directory=args.output/('check-'+label+'-'+suite)
        answer=evaluator.evaluate(TASK,args.source,args.assets,args.image,candidate,suite,directory,args.evaluation_lock)
        # The host wrapper checks artifact, world inventory and source provenance.
        if answer.get('operator_status') != 'completed' or answer.get('provenance_verified') is not True:
            raise RuntimeError('Evaluation infrastructure: '+label)
        raw=json.loads(Path(answer['result_path']).read_text())
        f=feedback(raw)
        if f['infrastructure_affected'] or not f['provenance_verified']:
            raise RuntimeError('Evaluation provenance: '+label)
        return raw,f,directory
    try:
        for label,candidate,expected in [
            ('reference',TASK/'controller/reference',args.old_reference_dev),
            ('incumbent',initial.parent,args.old_sol_dev)]:
            raw,f,directory=evaluate(label,candidate,'dev')
            if not same_game(json.loads(expected.read_text()),raw):
                raise RuntimeError('Initial development replay does not match: '+label)
            row={'label':label,'candidate':str(candidate),'sha256':sha(candidate/'controller.py'),
                 'feedback':f,'check':str(directory),'deployment_parity':True}
            records.append(row);history.append({'label':label,**f});save()
            print(json.dumps({'event':'initial_dev','label':label,'score':f['primary_score']}),flush=True)
        latest=initial.read_text()
        for index in range(1,CALLS+1):
            if not unchanged():raise RuntimeError('Study input changed')
            best=winner(records)
            best_code=candidate_bytes(best).decode('utf-8')
            status.update(phase='model_generation',calls_attempted=index);save()
            print(json.dumps({'event':'call_started','call':index}),flush=True)
            response=backend.infer(prompt(packet,latest,best_code,history,index),
                args.output/f'call-{index:02d}',SCHEMA,timeout=1800)
            if set(response)!={'controller','note'} or any(not isinstance(v,str) for v in response.values()):
                raise ValueError('Malformed response; no replacement call')
            candidate=args.output/f'candidate-{index:02d}';candidate.mkdir()
            (candidate/'controller.py').write_text(response['controller'])
            latest=response['controller']; expected_sha=sha(candidate/'controller.py')
            status['phase']='development_evaluation';save()
            if (candidate/'controller.py').stat().st_size > MAX_CANDIDATE:
                directory=args.output/f'check-{index:02d}-dev';directory.mkdir()
                f={'status':'unscored','total':4,'scored':0,'primary_score':None,
                   'diagnostic_counts':{'candidate_source_exceeds_1_mib':1},
                   'infrastructure_affected':False,'execution_attempted':False}
                dump(directory/'candidate-invalid.json',f)
            else:
                raw,f,directory=evaluate(f'{index:02d}',candidate,'dev')
            if sha(candidate/'controller.py')!=expected_sha:raise RuntimeError('Candidate changed')
            records.append({'label':f'call-{index:02d}','candidate':str(candidate),
                'sha256':expected_sha,'feedback':f,'check':str(directory)})
            history.append({'label':f'call-{index:02d}',**f});save()
            print(json.dumps({'event':'development_result','call':index,'feedback':f,
                              'best':winner(records)['label']}),flush=True)
        selected=winner(records)
        selected_dir=args.output/'selected';selected_dir.mkdir()
        (selected_dir/'controller.py').write_bytes(candidate_bytes(selected))
        status['selected']={k:selected[k] for k in ('label','sha256','feedback')}
        status['selected']['frozen_at_unix']=time.time()
        dump(args.output/'selection.json',status['selected'])
        status['phase']='final_comparisons';save()
        candidates=[('reference',TASK/'controller/reference',records[0]['sha256']),
                    ('incumbent',initial.parent,records[1]['sha256']),
                    ('selected',selected_dir,selected['sha256'])]
        if selected['sha256']!=sha(TASK/'controller/reference/controller.py'):
            ablations=module('alem_continuation_ablations',HERE/'make_ablations.py')
            for mode in ablations.MODES:
                destination=args.output/('ablation-'+mode)
                try:
                    built=ablations.build(selected_dir/'controller.py',destination,mode)
                    candidates.append((mode,destination,built['wrapped_sha256']))
                except (ValueError,SyntaxError,UnicodeError) as exc:
                    status.setdefault('unavailable_ablations',[]).append(
                        {'intervention':mode,'status':'unscored','error_type':type(exc).__name__})
        else:status['ablation_status']='not_run_selected_pass_through'
        reused={}
        for suite in ('evaluation','transfer'):
            for label,candidate,expected_sha in candidates:
                candidate_bytes({'candidate':str(candidate),'sha256':expected_sha})
                key=(expected_sha,suite)
                if key in reused:
                    final.append({'label':label,'suite':suite,'sha256':key[0],
                                  'reused_from':reused[key]['label'],'feedback':reused[key]['feedback'],
                                  'check':reused[key]['check']})
                else:
                    raw,f,directory=evaluate(label,candidate,suite)
                    candidate_bytes({'candidate':str(candidate),'sha256':expected_sha})
                    row={'label':label,'suite':suite,'sha256':key[0],
                         'feedback':f,'check':str(directory)}
                    reused[key]=row;final.append(row)
                save();print(json.dumps({'event':'final_result',**final[-1]}),flush=True)
        status['status']='completed';status['phase']='complete'
    except BaseException as exc:
        status.update(status='incomplete',error_type=type(exc).__name__)
        raise
    finally:
        status['source_unchanged']=unchanged()
        if not status['source_unchanged']:status['status']='unscored_source_changed'
        save()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('packet','source','assets','evaluation-lock','output','old-reference-dev','old-sol-dev'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--image',required=True)
    a=p.parse_args()
    for name in ('packet','source','assets','evaluation_lock','output','old_reference_dev','old_sol_dev'):
        setattr(a,name,getattr(a,name).resolve())
    execute(a)

if __name__=='__main__':main()

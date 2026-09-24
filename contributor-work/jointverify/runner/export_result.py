"""Publish only explicitly allowlisted experiment evidence; never raw model events."""
import argparse
import hashlib
import json
from pathlib import Path


def export(raw):
    raw=Path(raw)
    config=json.loads((raw/'run_config.json').read_text())
    status=json.loads((raw/'status.json').read_text())
    budget=json.loads((raw/'budget.json').read_text())
    judged=status.get('result',{})
    calls=[]
    for directory in sorted(raw.glob('call-*')):
        metadata=json.loads((directory/'metadata.json').read_text())
        call={key:metadata[key] for key in ('model_requested','reasoning_effort','model_identity_source',
            'seconds','tool_free','usage','status','measurement_type') if key in metadata}
        for filename in ('prompt.txt','response.json'):
            path=directory/filename
            if path.exists():call[filename.replace('.','_')+'_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        call['call']=directory.name
        calls.append(call)
    features={}
    for feature,result in judged.get('feature_checks',{}).items():
        features[feature]={key:result[key] for key in ('validinfra','passed','coverage_matches_oracle') if key in result}
        features[feature]['counts']={key:value for key,value in (result.get('test_counts') or {}).items() if key!='case_ids'}
    out={
        'schema_version':1,'run_id':raw.name,
        'measurement_type':status['measurement_type'],'status':status['status'],
        'configuration':config,
        'elapsed_seconds':status.get('elapsed_seconds'),
        'budget':{key:value for key,value in budget.items() if key not in ('calls','tools')},
        'calls':calls,
        'result':{key:judged[key] for key in ('validinfra','candidate_valid','both_features_passed',
            'manifest_sha256','merged_patch_sha256') if key in judged},
        'feature_results':features,
        'merge':{key:judged.get('merge',{}).get(key) for key in ('merge_strategy','fallback_reason')
                 if key in judged.get('merge',{})},
        'patch_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in raw.glob('*.patch')},
        'work_stop':{key:status[key] for key in ('work_stop','episode_time_limit_reached','tool_time_limit_reached') if key in status},
        'reporting_note':'Allowlisted summary. Raw events, reasoning, prompts, test traces and local paths remain local. CLI model identity is not an immutable server checkpoint.'
    }
    # Operational errors may contain local paths or model/backend payloads. Report
    # their category here; preserve full evidence locally for diagnosis.
    if 'error_type' in status:out['error_type']=status['error_type']
    if 'worker_failure' in status:out['worker_failure']=True
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=export(args.raw)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(args.output)

if __name__=='__main__':main()

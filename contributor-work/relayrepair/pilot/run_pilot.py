"""Run the preregistered nine-call, one-model feasibility smoke test."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sys
from pathlib import Path
from codex_runner import infer, batch_schema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'prototype'))
from relayrepair import evaluate_answer

RULES = '''This is a text-only smoke test. Use no tools, files, web, or outside knowledge.
All needed facts are in this prompt. Solve each case separately. Case IDs label independent worlds.
The domain instructions below define the logic. Override their output instruction with the batch JSON schema.
No information not supplied to you is available. Preserve source revision numbers in messages.
Messages can contain structured data. There is no hard communication token cap in this pilot.
'''


def index(response, ids, field):
    rows = response['results']
    if len(rows) != len(ids) or {r['case_id'] for r in rows} != set(ids):
        raise ValueError('Missing, duplicate, or unknown case IDs; this call is invalid, not scored as reasoning.')
    return {r['case_id']: r[field] for r in rows}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    generated = ROOT / 'prototype' / 'generated'
    observations = json.loads((generated/'model_observations.json').read_text())
    cases = json.loads((generated/'cases_with_oracle.json').read_text())
    ids = [c['case_id'] for c in cases]
    manifest = {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [generated/'model_observations.json', generated/'cases_with_oracle.json',
                             ROOT/'prototype'/'relayrepair.py', ROOT/'pilot'/'PROTOCOL.md',
                             Path(__file__).resolve(), ROOT/'pilot'/'codex_runner.py']}
    (args.output/'frozen_sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
    domain = observations[0]['observations']['initial']['instructions']
    domain = domain.replace('You may exchange evidence and use local code.', 'This pilot permits only the supplied text messages; use no tools or local code.')
    domain = domain.replace('Output one JSON object with exactly the key plan_id.', 'Follow the batch output schema supplied for your role.')
    rules = RULES + '\nDOMAIN:\n' + domain

    def worker(role, phase, previous=None):
        condition = 'initial' if phase == 0 else 'final_shuffled'
        payload=[]
        for c in observations:
            view=c['observations'][condition]
            private=next(r['private_cards'] for r in view['roles'] if r['role_id']==role)
            record={'case_id':c['case_id'],'public_cards':view['public_cards'],'your_private_cards':private}
            if previous is not None:
                record['previous_round_team_messages']={r: previous[r][c['case_id']] for r in previous}
            payload.append(record)
        prompt=rules+f'\nYou are {role}, one of three evidence owners. This is round {phase}. '
        prompt+='Write a message for a coordinator who sees only public plan cards and team messages. '
        prompt+='Communicate all information needed to select the best eligible plan. '
        prompt+='You may state facts, rules, sources, revisions, and necessary corrections; do not assume private cards held by teammates. '
        prompt+='Return {"results":[{"case_id":"...","message":"..."}]} covering every case.\n'
        prompt+=json.dumps(payload)
        response=infer(prompt,args.output/f'round{phase}-{role}',batch_schema('message'))
        print(f'finished round{phase} {role}',flush=True)
        return index(response,ids,'message')

    roles=['agent_1','agent_2','agent_3']
    with ThreadPoolExecutor(max_workers=3) as pool:
        fut={role:pool.submit(worker,role,0) for role in roles}
        initial={role:future.result() for role,future in fut.items()}

    def leader(phase, current, previous=None):
        payload=[]
        for c in observations:
            record={'case_id':c['case_id'],'public_cards':c['observations']['initial']['public_cards']}
            record['delivered_messages']=[{'origin_round':phase,'sender':role,'message':current[role][c['case_id']]} for role in roles]
            if previous is not None:
                record['delivered_messages'] += [{'origin_round':0,'sender':role,'message':previous[role][c['case_id']]} for role in roles]
            payload.append(record)
        prompt=rules+f'\nYou are the coordinator, selecting the current highest-utility eligible plan in round {phase}. '
        prompt+='In round 1 the old round-0 messages are honestly tagged delayed retransmissions, not later evidence. '
        prompt+='Select exactly one plan per case. Return {"results":[{"case_id":"...","plan_id":"..."}]}.\n'+json.dumps(payload)
        response=infer(prompt,args.output/f'round{phase}-leader',batch_schema('plan_id'))
        print(f'finished round{phase} leader',flush=True)
        return index(response,ids,'plan_id')

    initial_answer=leader(0,initial)
    with ThreadPoolExecutor(max_workers=3) as pool:
        fut={role:pool.submit(worker,role,1,initial) for role in roles}
        updated={role:future.result() for role,future in fut.items()}
    final_answer=leader(1,updated,initial)
    payload=[{'case_id':c['case_id'],'cards':c['observations']['final_shuffled']['central_cards']} for c in observations]
    prompt=rules+'\nYou have all roles\' original evidence, including revisions and delayed cards. Select the current highest-utility eligible plan for every case. Return {"results":[{"case_id":"...","plan_id":"..."}]}.\n'+json.dumps(payload)
    central=index(infer(prompt,args.output/'centralized-final',batch_schema('plan_id')),ids,'plan_id')
    rows=[]
    for config,condition,predictions in [('team_initial','initial',initial_answer),('team_final','final_shuffled',final_answer),('centralized_final','final_shuffled',central)]:
        for c in cases:
            rows.append({'configuration':config,'case_id':c['case_id'],'mechanism':c['mechanism'],**evaluate_answer(c,condition,predictions[c['case_id']])})
    summary=[]
    for config in ['team_initial','team_final','centralized_final']:
        for mechanism in ['all','required_support_lost','alternate_support_survives','irrelevant_revision']:
            selected=[r for r in rows if r['configuration']==config and (mechanism=='all' or r['mechanism']==mechanism)]
            summary.append({'configuration':config,'mechanism':mechanism,'correct':sum(r['exact_success'] for r in selected),'n':len(selected),'feasible':sum(r['valid_plan'] for r in selected)})
    result={'measurement_type':'ONE_MODEL_BATCHED_SMOKE_TEST_NOT_BENCHMARK_VALIDATION','summary':summary,'rows':rows}
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__': main()

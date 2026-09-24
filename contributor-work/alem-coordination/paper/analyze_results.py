"""Recompute descriptive tables from both verified public exports; no execution."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUITES = ('dev', 'evaluation', 'transfer')
ORDER = ['reference', 'incumbent'] + [f'call-{i:02d}' for i in range(1, 7)]
METRICS = {
    'ordinary_reward': 'Team/normal_reward_pct_of_max',
    'total_reward': 'Team/reward_pct_of_max',
    'soft_coordination': 'Team/soft_coord_reward_pct_of_max',
    'hard_coordination': 'Team/sync_hard_coord_reward_pct_of_max',
    'handover': 'Team/handover_coord_reward_pct_of_max',
    'construction': 'Team/construction_coord_reward_pct_of_max',
}


class Export:
    def __init__(self, directory):
        self.directory = directory
        raw = (directory / 'MANIFEST.json').read_bytes()
        self.manifest_sha256 = hashlib.sha256(raw).hexdigest()
        self.files = json.loads(raw)['files']

    def read(self, name):
        raw = (self.directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != self.files[name]:
            raise ValueError('changed_public_export: ' + name)
        return json.loads(raw)


def paired(left, right):
    if left['world_ids'] != right['world_ids']:
        raise ValueError('different_world_lists')
    worlds = []
    valid = left['status'] == right['status'] == 'scored'
    for a, b in zip(left['worlds'], right['worlds']):
        valid_pair = a['status'] == b['status'] == 'scored'
        worlds.append({'world_id': a['world_id'], 'difference': a['score'] - b['score'] if valid_pair else None})
        valid = valid and valid_pair
    values = [w['difference'] for w in worlds]
    if not valid:
        return {'mean_difference': None, 'worlds': worlds}
    mean = sum(values) / len(values)
    if not math.isclose(mean, left['primary_score'] - right['primary_score'], abs_tol=1e-12):
        raise ValueError('paired_mean_mismatch')
    return {'mean_difference': mean, 'better': sum(x > 0 for x in values),
            'tied': sum(x == 0 for x in values), 'worse': sum(x < 0 for x in values),
            'worlds': worlds}


def checked(data):
    if [w['world_id'] for w in data['worlds']] != data['world_ids']:
        raise ValueError('world_inventory_mismatch')
    if data['status'] == 'scored':
        if not all(w['status'] == 'scored' and math.isfinite(w['score']) for w in data['worlds']):
            raise ValueError('partial_scored_suite')
        mean = sum(w['score'] for w in data['worlds']) / len(data['worlds'])
        if not math.isclose(mean, data['primary_score'], abs_tol=1e-12):
            raise ValueError('mean_mismatch')
    elif data['primary_score'] is not None:
        raise ValueError('unscored_suite_has_mean')
    return data


def label(name):
    return {'reference': 'Unchanged reference — selected', 'incumbent': 'Original Sol'}.get(name, 'New call ' + name[-1])


def main():
    base = Export(ROOT / 'results/sol-continuation-001')
    extra = Export(ROOT / 'results/sol-trajectory-diagnostic-001')
    main_summary, diagnostic = base.read('summary.json'), extra.read('summary.json')
    if main_summary['audit_status'] != 'verified' or diagnostic['status'] not in ('completed', 'unscored_infrastructure'):
        raise ValueError('unverified_inputs')
    if diagnostic['main_selection_unchanged'] != main_summary['selection']:
        raise ValueError('selection_mismatch')
    records = {}
    for row in main_summary['development']:
        records[(row['label'], 'dev')] = checked(base.read('evaluations/' + row['evaluation'] + '.json'))
    for row in main_summary['final']:
        if row['label'] in ('reference', 'incumbent'):
            records[(row['label'], row['suite'])] = checked(base.read('evaluations/' + row['evaluation'] + '.json'))
    for row in diagnostic['candidates']:
        for suite, record in row['suites'].items():
            data = checked(extra.read(record['evaluation']))
            if data['candidate_sha256'] != records[(row['label'], 'dev')]['candidate_sha256']:
                raise ValueError('candidate_changed_between_suites')
            records[(row['label'], suite)] = data
    rows = []
    for name in ORDER:
        row = {'label': name, 'suites': {}}
        for suite in SUITES:
            data = records[(name, suite)]
            costs = {key: (sum(w['costs'][key] for w in data['worlds'])
                           if all(key in w.get('costs', {}) for w in data['worlds']) else None)
                     for key in ('steps', 'action_count', 'overrides', 'native_communication_actions')}
            row['suites'][suite] = {
                'status': data['status'], 'score': data['primary_score'], 'costs': costs,
                'reward_components': {k: data.get('metrics_mean', {}).get(v) for k, v in METRICS.items()},
                'native_diagnostics_mean': {key: data.get('metrics_mean', {}).get(key) for key in
                    ('Cooperation/alive_agent_steps', 'Cooperation/actionable_agent_steps',
                     'Coordination/sync_attempts', 'Coordination/sync_successes')},
                'minus_reference': paired(data, records[('reference', suite)]),
                'minus_incumbent': paired(data, records[('incumbent', suite)]),
            }
        rows.append(row)
    output = {'scope': 'Descriptive recomputation of all fixed programs; no retrospective reselection',
              'selection': main_summary['selection'], 'rows': rows,
              'main_manifest_sha256': base.manifest_sha256, 'diagnostic_manifest_sha256': extra.manifest_sha256,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'score_unit': 'fraction of coordination reward; multiply by 100 for percent',
              'tie_rule': 'exact equality of recorded floating-point scores',
              'researcher_samples': 1, 'new_model_calls': 6,
              'input_plus_output_tokens': main_summary['input_plus_output_tokens']}
    (ROOT / 'study-analysis.json').write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + '\n')
    text = ['# Complete result table', '',
            'Scores are mean coordination reward percentages, not pass rates. All programs were fixed before final testing.',
            'The unchanged reference was selected using only four development worlds. The other final scores are descriptive;',
            'they do not select a new winner. The six new programs belong to one dependent research attempt.', '',
            '| Program | Development (4) | Original worlds (20) | Fresh worlds (20) |',
            '| --- | ---: | ---: | ---: |']
    for row in rows:
        scores = [f"{row['suites'][suite]['score'] * 100:.4f}%" if row['suites'][suite]['score'] is not None else 'Unscored' for suite in SUITES]
        text.append('| ' + label(row['label']) + ' | ' + ' | '.join(scores) + ' |')
    text += ['', '## Paired changes on fresh worlds', '',
             'Each comparison uses the same twenty world IDs. Positive means the named program scored more.',
             'Counts use exact equality of recorded scores; tiny floating-point differences can count as changes.', '',
             '| Program | Gain over reference (percentage points) | Better / tied / worse | Gain over original Sol (percentage points) |',
             '| --- | ---: | ---: | ---: |']
    for row in rows:
        a = row['suites']['transfer']['minus_reference']
        b = row['suites']['transfer']['minus_incumbent']
        if a['mean_difference'] is None or b['mean_difference'] is None:
            text.append(f"| {label(row['label'])} | Unscored | — | Unscored |")
        else:
            text.append(f"| {label(row['label'])} | {a['mean_difference'] * 100:+.4f} | {a['better']} / {a['tied']} / {a['worse']} | {b['mean_difference'] * 100:+.4f} |")
    text += ['', '## Actions and reward components on fresh worlds', '',
             'Action changes and message counts describe whole trajectories. Changing one action can change later states,',
             'survival and opportunities, so these counts do not identify the cause of a reward difference.',
             'Reward components use their own native denominators; their percentages must not be added together.', '',
             '| Program | Changed actions / all actions | Native messages | Ordinary reward | Soft coordination | Hard synchronous coordination | Handover | Construction |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in rows:
        data = row['suites']['transfer']; c = data['costs']; m = data['reward_components']
        values = [f'{m[k] * 100:.4f}%' if m[k] is not None else 'Unscored' for k in ('ordinary_reward', 'soft_coordination', 'hard_coordination', 'handover', 'construction')]
        text.append(f"| {label(row['label'])} | {c['overrides']} / {c['action_count']} | {c['native_communication_actions']} | " + ' | '.join(values) + ' |')
    text += ['', 'The [machine-readable analysis](study-analysis.json) contains all paired differences on all three sets,',
             'including every regression, reward components and action counts. The source exports retain per-world metrics,',
             'runtime costs, exact code and provenance. [analyze_results.py](analyze_results.py) verifies export file hashes',
             'and recomputes the scores and comparisons without importing or executing any controller.', '',
             'These are fixed-set descriptions. We report no confidence intervals or population-level model ranking.', '']
    (ROOT / 'RESULTS.md').write_text('\n'.join(text))
    print(json.dumps({'programs': len(rows), 'suites': len(SUITES), 'selection': output['selection']['label']}))


if __name__ == '__main__':
    main()

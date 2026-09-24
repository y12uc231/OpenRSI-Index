"""Compare the public original pilot and continuation on their shared worlds."""
import hashlib
import json
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]


def main():
    new_root = TASK / 'paper/results/sol-continuation-001'
    manifest = json.loads((new_root / 'MANIFEST.json').read_text())
    result = {'scope': 'Original 20-world deterministic replay', 'arms': [],
              'excludes_variable_costs': ['seconds', 'ipc_seconds'],
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    for label, old_name in [('reference', 'native/evidence/full20-pass-through.json'),
                            ('incumbent', 'results/sol-001/final-evaluation.json')]:
        new_name = f'evaluations/evaluation-{label}.json'
        old_raw = (TASK / old_name).read_bytes()
        new_raw = (new_root / new_name).read_bytes()
        assert hashlib.sha256(new_raw).hexdigest() == manifest['files'][new_name]
        old, new = json.loads(old_raw), json.loads(new_raw)
        old_sha = old['source_hashes']['candidate_sha256'] if label == 'reference' else old['candidate_sha256']
        assert old_sha == new['candidate_sha256']
        assert [r['world_id'] for r in old['worlds']] == new['world_ids'] == list(range(9999, 10019))
        checked = []
        for a, b in zip(old['worlds'], new['worlds']):
            for key in ('world_id', 'status', 'trace_sha256', 'naturally_terminated', 'diagnostic_code', 'error_type'):
                assert a.get(key) == b[key], (label, a['world_id'], key)
            for key, value in a.get('metrics', a.get('reward_fraction')).items():
                assert value == b['metrics'][key], (label, a['world_id'], key)
            for key, value in a.get('native_diagnostics', {}).items():
                assert value == b['metrics'][key], (label, a['world_id'], key)
            for key, value in a['costs'].items():
                if key not in ('seconds', 'ipc_seconds'):
                    assert value == b['costs'][key], (label, a['world_id'], key)
            checked.append(a['world_id'])
        result['arms'].append({'label': label, 'original_file': old_name,
                               'original_sha256': hashlib.sha256(old_raw).hexdigest(),
                               'continuation_file': 'results/sol-continuation-001/' + new_name,
                               'continuation_sha256': hashlib.sha256(new_raw).hexdigest(),
                               'worlds': checked, 'all_compared_fields_equal': True})
    result['status'] = 'verified'
    destination = TASK / 'paper/original-replay-check.json'
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('Verified 40 trajectories: trace hashes, reward, native diagnostics and discrete costs match.')


if __name__ == '__main__':
    main()

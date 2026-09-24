"""Run base, oracle, independent-gold and public smoke controls; no models."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
from datetime import datetime, timezone

from .checker import DEFAULT_SOURCE, ROOT, asset_bytes, evaluate, load_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output-dir', type=Path, required=True, help='Local raw evidence directory outside the contribution checkout')
    args = parser.parse_args()
    if ROOT.parents[1] in args.output_dir.resolve().parents:
        parser.error('Keep raw reference patches/test logs outside the contribution checkout; publish summary.json only')
    summaries = []
    for case in load_manifest()['cases']:
        task = case['task_id']
        oracle = asset_bytes(args.source_root, case['oracle_patch']).decode()
        task_directory = args.source_root / Path(case['oracle_patch']['path']).parent
        individual = [(task_directory / f'feature{f}' / 'feature.patch').read_text() for f in case['features']]
        controls = [('base', '', '', 'judge'), ('oracle', oracle, oracle, 'judge'),
                    ('independent_gold', *individual, 'judge'), ('public_base', '', '', 'public')]
        for label, lead, member, mode in controls:
            result = evaluate(task, {'lead': lead, 'member': member}, mode,
                              source_root=args.source_root,
                              output_path=args.output_dir / f'{task}.{label}.json')
            summary = {'task_id': task, 'control': label, 'validinfra': result['validinfra'],
                       'passed': result.get('both_features_passed', result.get('public_passed')),
                       'merge_strategy': result.get('merge', {}).get('merge_strategy'),
                       'features': {f: {k: v for k, v in (c.get('test_counts') or {}).items() if k != 'case_ids'}
                                    for f, c in result.get('feature_checks', {}).items()},
                       'input_patch_sha256': [hashlib.sha256(p.encode()).hexdigest() for p in [lead, member]]}
            summaries.append(summary)
            print(json.dumps(summary), flush=True)
    metadata = {'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                'host_system': platform.system(), 'host_architecture': platform.machine(),
                'container_limits': {'cpus': 2, 'memory_gib': 2, 'pids': 256, 'network': 'none'},
                'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((ROOT / 'evaluator').glob('*.py'))},
                'manifest_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted((ROOT / 'manifests').glob('*.json'))},
                'coverage_note': 'Normalize only the pinned Dirty Equals base UUID1 parameter; exact counts and other identities.',
                'controls_only_no_model_calls': True, 'results': summaries}
    (args.output_dir / 'summary.json').write_text(json.dumps(metadata, indent=2) + '\n')
    assert all(r['validinfra'] for r in summaries), 'Infrastructure failure in controls'
    assert all(r['passed'] for r in summaries if r['control'] in ['oracle', 'public_base'])
    assert not any(r['passed'] for r in summaries if r['control'] == 'base')


if __name__ == '__main__':
    main()

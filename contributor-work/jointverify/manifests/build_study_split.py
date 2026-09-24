#!/usr/bin/env python3
"""Deterministic source-only study selection; never reads model scores."""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

UPSTREAM_COMMIT = '63b9d44d9f39a02fccf5bf0052db48a917a011fd'
SALT = 'jointverify-v1:'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def build(all_path, tree_path, pilot_path):
    source = json.loads(all_path.read_text())
    tree = json.loads(tree_path.read_text())
    pilot = json.loads(pilot_path.read_text())
    if tree.get('truncated') or tree.get('sha') != UPSTREAM_COMMIT:
        raise ValueError('Need a complete GitHub tree for the pinned upstream commit.')
    if pilot['upstream_commit'] != UPSTREAM_COMMIT:
        raise ValueError('Pilot source pin differs.')
    indexed = {entry['path']: entry for entry in tree['tree']}
    by_repo = defaultdict(list)
    seen = set()
    for task in source['tasks']:
        repo, number = task['repo'], str(task['task_id'])
        for raw in task['pairs']:
            pair = tuple(sorted(raw))
            key = (repo, number, pair)
            if len(pair) != 2 or pair[0] == pair[1] or key in seen:
                raise ValueError('Unexpected duplicate/invalid upstream feature pair.')
            seen.add(key)
            by_repo[repo].append((number, pair))
    if len(seen) != 652 or len(by_repo) != 12 or len(source['tasks']) != 30:
        raise ValueError('Pinned source cardinality changed.')

    forced = {case['repository'] for case in pilot['cases']}
    if not forced <= set(by_repo) or len(forced) > 8:
        raise ValueError('Prior pilot repositories cannot all be assigned to development.')
    order = sorted(by_repo, key=lambda repo: digest(SALT + repo))
    remainder = [repo for repo in order if repo not in forced]
    dev = forced | set(remainder[:8 - len(forced)])
    groups = {'development': [repo for repo in order if repo in dev],
              'evaluation': [repo for repo in order if repo not in dev]}

    def artifact(path, visibility, required=True):
        entry = indexed.get(path)
        return {'path': path, 'visibility': visibility, 'required_source_asset': required,
                'present_in_pinned_git_tree': entry is not None and entry.get('type') == 'blob',
                'git_blob_sha1': entry.get('sha') if entry else None,
                'size_bytes': entry.get('size') if entry else None,
                'source_url': f'https://github.com/cooperbench/CooperBench/blob/{UPSTREAM_COMMIT}/{path}'}

    cases = []
    for split, repositories in groups.items():
        for repo in repositories:
            tasks = defaultdict(list)
            for number, pair in by_repo[repo]:
                tasks[number].append(pair)
            task_order = sorted(tasks, key=lambda number: digest(SALT + 'task:' + repo + ':' + number))
            for number, pairs in tasks.items():
                pairs.sort(key=lambda pair: digest(SALT + 'pair:' + repo + ':' + number + ':' + ':'.join(map(str, pair))))
            selection = []
            depth = 0
            while len(selection) < 3:
                added = False
                for number in task_order:
                    if depth < len(tasks[number]) and len(selection) < 3:
                        selection.append((number, tasks[number][depth]))
                        added = True
                if not added:
                    break
                depth += 1
            for number, pair in selection:
                folder = f'dataset/{repo}/task{number}'
                raw_id = f'{repo}/{number}/{pair[0]}_{pair[1]}'
                artifacts = [artifact(folder + '/Dockerfile', 'controller'),
                             artifact(folder + '/combined.patch', 'judge_only'),
                             artifact(folder + '/runner.sh', 'judge_only', required=False),
                             artifact(folder + '/run_tests.sh', 'judge_only', required=False)]
                for feature in pair:
                    prefix = folder + f'/feature{feature}'
                    artifacts += [artifact(prefix + '/feature.md', 'worker_assigned_feature'),
                                  artifact(prefix + '/tests.patch', 'judge_only'),
                                  artifact(prefix + '/feature.patch', 'judge_only', required=False)]
                cases.append({'raw_id': raw_id, 'split': split, 'repository': repo, 'task_number': number,
                              'features': list(pair), 'source_task_path': folder,
                              'selection_sha256': digest(SALT + 'pair:' + repo + ':' + number + ':' + ':'.join(map(str, pair))),
                              'artifacts': artifacts,
                              'source_presence_check': all(a['present_in_pinned_git_tree'] for a in artifacts if a['required_source_asset']),
                              'execution_validation': 'Not performed for this study selection; see separate pilot validation only.',
                              'image_digest': None})
    if set(groups['development']) & set(groups['evaluation']):
        raise AssertionError('Repository leakage.')
    if len(cases) != 36:
        raise AssertionError('Expected exactly three available source pairs per repository.')
    return {'schema_version': 1, 'status': 'proposed_frozen_source_selection_not_runtime_validated',
            'upstream': 'https://github.com/cooperbench/CooperBench', 'upstream_commit': UPSTREAM_COMMIT,
            'upstream_manifest': {'path': 'dataset/subsets/all.json', 'sha256': hashlib.sha256(all_path.read_bytes()).hexdigest(),
                                  'git_blob_sha1': indexed['dataset/subsets/all.json']['sha'],
                                  'pairs': 652, 'base_tasks': 30, 'repositories': 12},
            'prior_pilot': {'path': 'pilot-v1.json', 'sha256': hashlib.sha256(pilot_path.read_bytes()).hexdigest(),
                            'forced_development_repositories': sorted(forced),
                            'rule': 'Assign every repository used by the existing pilot to development before hashing remaining repositories.'},
            'selection_rule': {'salt': SALT, 'repository_order': 'ascending SHA256(salt + repository)',
                               'development': 'forced pilot repositories plus earliest remaining repositories until eight total',
                               'evaluation': 'the other four repositories', 'pairs_per_repository': 3,
                               'base_task_order': 'ascending SHA256(salt + task: + repo + : + task_id)',
                               'pair_order': 'ascending SHA256(salt + pair: + repo + : + task_id + : + feature_a + : + feature_b)',
                               'balancing': 'round-robin across ordered base tasks, choosing the next hashed pair per task until three pairs',
                               'outcome_filtering': 'none; no model result, difficulty label, test outcome or learned policy is read',
                               'replacement_policy': 'none in v1; later infrastructure exclusions/replacements require an explicit new version and fixed outcome-independent rule'},
            'repositories': groups, 'counts': {'development_pairs': 24, 'evaluation_pairs': 12},
            'visibility': 'Manifest/public upstream assets are globally public; evaluation task assets and per-case outcomes are withheld from the outer Work process under the declared runtime contract. Repeated aggregate Judge feedback creates adaptive-overfitting risk.',
            'validation_boundary': 'Only immutable Git-tree asset presence/hashes checked here. No new image pulls, tests or model calls. Runtime coverage is limited to separately documented three pilot cases.',
            'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', type=Path, required=True, dest='all_path')
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--pilot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.all_path, args.tree, args.pilot)
    data = (json.dumps(result, indent=2) + '\n').encode()
    args.output.write_bytes(data)
    args.output.with_suffix('.sha256').write_text(hashlib.sha256(data).hexdigest() + '  ' + args.output.name + '\n')
    print(json.dumps({'counts': result['counts'], 'repositories': result['repositories'],
                      'required_source_assets_present': all(c['source_presence_check'] for c in result['cases'])}))


if __name__ == '__main__':
    main()

"""Host API for the frozen three-pair pilot. Python standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'manifests' / 'pilot-v1.json'
DEFAULT_SOURCE = Path(os.environ.get('JOINTVERIFY_SOURCE_ROOT', 'CooperBench'))


def load_manifest():
    expected = MANIFEST.with_suffix('.sha256').read_text().split()[0]
    if hashlib.sha256(MANIFEST.read_bytes()).hexdigest() != expected:
        raise ValueError('pilot manifest hash mismatch')
    return json.loads(MANIFEST.read_text())


def get_case(task_id):
    return next(case for case in load_manifest()['cases'] if case['task_id'] == task_id)


def asset_bytes(source_root, asset):
    data = (Path(source_root) / asset['path']).read_bytes()
    if hashlib.sha256(data).hexdigest() != asset['sha256']:
        raise ValueError('upstream asset hash mismatch: ' + asset['path'])
    return data


def check_judge_coverage(task_id, feature, check):
    path = ROOT / 'manifests' / 'judge-expectations-v1.json'
    expected_digest = path.with_suffix('.sha256').read_text().split()[0]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_digest:
        raise ValueError('judge calibration hash mismatch')
    expected = json.loads(path.read_text())['cases'][task_id][str(feature)]
    actual = check.get('test_counts') or {}
    def stable_ids(ids):
        # The pinned Dirty Equals base suite creates uuid.uuid1() at collection.
        # Normalize that one known parameter only; retain every case and count.
        return sorted(re.sub(r'^(tests\.test_other::test_is_uuid_true\[)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(-dirty9\])$',
                             r'\1<DYNAMIC-UUID1>\2', item) for item in ids)
    match = (all(actual.get(key) == expected[key] for key in ['total', 'passed', 'skipped'])
             and stable_ids(actual.get('case_ids', [])) == stable_ids(expected['case_ids']))
    check['coverage_matches_oracle'] = match
    check['passed'] = check.get('passed', False) and match
    check['expectations_sha256'] = expected_digest
    return check


def checked_patch(patch, case, mode):
    """Reject unsafe/unsupported diff forms; remove candidate tests in judge mode."""
    if not patch.strip():
        return '', [], []
    if not patch.startswith('diff --git '):
        raise ValueError('patch must be a git unified diff')
    sections = re.split(r'(?=^diff --git )', patch, flags=re.M)
    kept, stripped, changed = [], [], []
    for section in sections:
        if not section:
            continue
        header = section.splitlines()[0]
        match = re.fullmatch(r'diff --git a/([^\s]+) b/([^\s]+)', header)
        if not match or match[1] != match[2]:
            raise ValueError('renames or quoted/whitespace paths are unsupported')
        path = match[1]
        p = PurePosixPath(path)
        if p.is_absolute() or '..' in p.parts or '\\' in path or any(part.startswith('.') for part in p.parts):
            raise ValueError('unsafe patch path: ' + path)
        if re.search(r'^(?:old mode|new mode|deleted file mode|rename |copy |GIT binary patch|Binary files)', section, re.M):
            raise ValueError('deletions, binary diffs, mode changes, renames and copies are unsupported')
        for line in section.splitlines():
            if line.startswith('new file mode ') and line != 'new file mode 100644':
                raise ValueError('new files must be ordinary non-executable files')
            if line.startswith('--- ') and line not in ('--- a/' + path, '--- /dev/null'):
                raise ValueError('old file header mismatch')
            if line.startswith('+++ ') and line != '+++ b/' + path:
                raise ValueError('new file header mismatch')
        is_test = path.startswith('tests/')
        if is_test and mode == 'judge':
            stripped.append(path)
            continue
        if not is_test and not any(path.startswith(prefix) for prefix in case['source_prefixes']):
            raise ValueError('path outside task source/test allowlist: ' + path)
        kept.append(section)
        changed.append(path)
    return ''.join(kept), sorted(set(stripped)), sorted(set(changed))


def _container(case, config, files, *, deadline=None):
    remaining = None if deadline is None else deadline - time.monotonic()
    if remaining is not None and remaining <= 0:
        return {'validinfra': False, 'budget_exhausted': True, 'error': 'evaluation wall-clock budget exhausted'}
    if remaining is not None:
        config = dict(config, test_timeout_seconds=min(config['test_timeout_seconds'], max(0.1, remaining - 1)))
    name = 'jointverify-' + uuid.uuid4().hex[:16]
    with tempfile.TemporaryDirectory(prefix='jointverify-') as temporary:
        tmp = Path(temporary)
        inputs, outputs = tmp / 'inputs', tmp / 'outputs'
        inputs.mkdir(mode=0o700)
        outputs.mkdir(mode=0o700)
        (inputs / 'config.json').write_text(json.dumps(config))
        for filename, content in files.items():
            (inputs / filename).write_bytes(content if isinstance(content, bytes) else content.encode())
        command = ['docker', 'run', '--rm', '--name', name, '--network', 'none',
                   '--cpus', '2', '--memory', '2g', '--pids-limit', '256',
                   '--security-opt', 'no-new-privileges', '--cap-drop', 'NET_RAW',
                   '--mount', f'type=bind,src={inputs},dst=/inputs,readonly',
                   '--mount', f'type=bind,src={outputs},dst=/outputs',
                   '--mount', f'type=bind,src={Path(__file__).with_name("container_check.py")},dst=/harness.py,readonly',
                   '--entrypoint', 'python', case['image'], '/harness.py']
        try:
            timeout = case['test_timeout_seconds'] + 45 if deadline is None else max(0.01, deadline - time.monotonic())
            process = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=timeout)
            output = outputs / 'result.json'
            if process.returncode or not output.exists():
                return {'validinfra': False, 'error': 'Docker/controller failure',
                        'docker_exit_code': process.returncode, 'log': process.stdout[-10000:]}
            result = json.loads(output.read_text())
            result['container_log'] = process.stdout[-3000:]
            return result
        except subprocess.TimeoutExpired:
            return {'validinfra': False, 'budget_exhausted': deadline is not None,
                    'error': 'evaluation wall-clock budget exhausted' if deadline is not None else 'container/controller timeout'}
        except OSError as exc:
            return {'validinfra': False, 'error': 'Docker unavailable: ' + str(exc)}
        finally:
            try:
                subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=3)
            except (subprocess.TimeoutExpired, OSError):
                pass


def evaluate(task_id, patches_by_worker, mode='public', *, source_root=DEFAULT_SOURCE, output_path=None, max_seconds=None):
    """Evaluate independent base-relative patches.

    patches_by_worker is {'lead': <diff string or Path>, 'member': <diff string or Path>}.
    The lead is fixed by the experiment protocol, never chosen after judging.
    Public mode never opens, copies or mounts upstream feature tests or oracle patches.
    """
    if mode not in ('public', 'judge'):
        raise ValueError('mode must be public or judge')
    deadline = None if max_seconds is None else time.monotonic() + max(0, max_seconds)
    case = get_case(task_id)
    result = {'schema_version': 1, 'task_id': task_id, 'mode': mode,
              'manifest_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
              'validinfra': True, 'candidate_valid': True, 'stripped_test_paths': [],
              'image': case['image'], 'base_commit': case['base_commit']}
    patches, changed = {}, []
    try:
        for worker in ('lead', 'member'):
            raw = patches_by_worker.get(worker, '')
            raw = raw.read_text() if isinstance(raw, Path) else raw
            patch, stripped, paths = checked_patch(raw, case, mode)
            patches[worker + '.patch'] = patch
            result['stripped_test_paths'].extend(stripped)
            changed.extend(paths)
    except (ValueError, OSError, TypeError) as exc:
        result.update(candidate_valid=False, error=str(exc))
        if mode == 'judge':
            result['both_features_passed'] = False
        else:
            result['public_passed'] = False
        return _save(result, output_path)
    config_base = {'base_commit': case['base_commit'], 'test_timeout_seconds': case['test_timeout_seconds']}
    config = dict(config_base, stage='merge')
    merged = _container(case, config, patches, deadline=deadline)
    result['merge'] = {key: value for key, value in merged.items() if key != 'merged_patch'}
    if not merged.get('validinfra') or not merged.get('candidate_valid', True):
        result.update(validinfra=merged.get('validinfra', False),
                      candidate_valid=merged.get('candidate_valid', True))
        if mode == 'judge':
            result['both_features_passed'] = False
        else:
            result['public_passed'] = False
        return _save(result, output_path)
    result['merged_patch'] = merged['merged_patch']
    result['merged_patch_sha256'] = merged['merged_patch_sha256']
    if mode == 'public':
        targets = sorted(set(case['public_test_targets'] + [p for p in changed if p.startswith('tests/') and p.endswith('.py')]))
        config = dict(config_base, stage='test', test_targets=targets)
        check = _container(case, config, {'merged.patch': merged['merged_patch']}, deadline=deadline)
        result.update(public_check=check, public_passed=check.get('passed', False),
                      validinfra=check.get('validinfra', False))
    else:
        results = {}
        for feature in case['features']:
            try:
                tests = asset_bytes(source_root, case['judge_test_patches'][str(feature)])
            except (OSError, ValueError) as exc:
                results[str(feature)] = {'validinfra': False, 'error': str(exc)}
                continue
            config = dict(config_base, stage='test', test_targets=case['public_test_targets'], judge_test_patch=True)
            check = _container(case, config, {'merged.patch': merged['merged_patch'], 'judge.patch': tests}, deadline=deadline)
            try:
                results[str(feature)] = check_judge_coverage(task_id, feature, check)
            except (OSError, ValueError, KeyError) as exc:
                results[str(feature)] = dict(check, validinfra=False, passed=False, error=str(exc))
        result['feature_checks'] = results
        result['validinfra'] = all(v.get('validinfra') for v in results.values())
        result['both_features_passed'] = result['validinfra'] and all(v.get('passed') for v in results.values())
    return _save(result, output_path)


def _save(result, output_path):
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id')
    parser.add_argument('--lead', type=Path)
    parser.add_argument('--member', type=Path)
    parser.add_argument('--mode', choices=['public', 'judge'], default='public')
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--max-seconds', type=float)
    args = parser.parse_args()
    result = evaluate(args.task_id, {'lead': args.lead or '', 'member': args.member or ''},
                      args.mode, source_root=args.source_root, output_path=args.output, max_seconds=args.max_seconds)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

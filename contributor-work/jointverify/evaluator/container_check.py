"""Trusted container entry point; no task runner or install commands are executed."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

REPO = Path('/workspace/repo')
INPUT = Path('/inputs')
OUTPUT = Path('/outputs')


def run(args, *, timeout=30, **kw):
    return subprocess.run(args, cwd=REPO, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout, **kw)


def git(*args):
    result = run(['git', *args])
    if result.returncode:
        raise RuntimeError('git ' + ' '.join(args) + ': ' + result.stdout[-6000:])
    return result.stdout.strip()


def reset(base):
    run(['git', 'merge', '--abort'])
    git('checkout', '--detach', '-f', base)
    git('reset', '--hard', base)
    git('clean', '-fdx')


def apply(path, *, test_patch=False, identical=False):
    flags = ['--ignore-whitespace', '--ignore-space-change'] if test_patch else []
    result = run(['git', 'apply', '--index', *flags, str(path)])
    if result.returncode and not test_patch:
        result = run(['git', 'apply', '--index', '--recount' if identical else '--3way', str(path)])
    if result.returncode:
        raise RuntimeError(result.stdout[-6000:])


def merge(config):
    base = config['base_commit']
    paths = [INPUT / 'lead.patch', INPUT / 'member.patch']
    patches = [p.read_text() for p in paths]
    git('config', 'user.name', 'JointVerify evaluator')
    git('config', 'user.email', 'evaluator@localhost.invalid')
    result = {'validinfra': True, 'merge_status': '', 'merge_strategy': '', 'log': ''}
    try:
        if patches[0] and patches[0] == patches[1]:
            reset(base)
            apply(paths[0], identical=True)
            result.update(merge_status='identical', merge_strategy='identical_once')
        else:
            tips = []
            for index, path in enumerate(paths):
                reset(base)
                if patches[index]:
                    apply(path)
                git('commit', '--allow-empty', '-m', f'worker {index}')
                tips.append(git('rev-parse', 'HEAD'))
            git('checkout', '--detach', '-f', tips[1])
            outcome = run(['git', 'merge', '--no-edit', '--no-ff', tips[0]])
            if outcome.returncode:
                result['log'] = outcome.stdout[-6000:]
                raise RuntimeError('merge conflict')
            result.update(merge_status='clean', merge_strategy='three_way')
    except RuntimeError as exc:
        result['log'] += '\n' + str(exc)
        reset(base)
        try:
            if patches[0]:
                apply(paths[0])
            result.update(merge_status='fallback', merge_strategy='lead_only')
        except RuntimeError as lead_error:
            result.update(merge_status='invalid_lead_patch', merge_strategy='none',
                          candidate_valid=False, log=result['log'] + '\n' + str(lead_error))
            return result
    patch = run(['git', 'diff', '--binary', base]).stdout
    result.update(candidate_valid=True, merged_patch=patch,
                  merged_patch_sha256=hashlib.sha256(patch.encode()).hexdigest())
    return result


def counts(xml):
    root = ET.fromstring(xml)
    cases = list(root.iter('testcase'))
    failure = sum(c.find('failure') is not None for c in cases)
    error = sum(c.find('error') is not None for c in cases)
    skipped = sum(c.find('skipped') is not None for c in cases)
    return {'total': len(cases), 'passed': len(cases) - failure - error - skipped,
            'failed': failure, 'errors': error, 'skipped': skipped,
            'case_ids': sorted(c.get('classname', '') + '::' + c.get('name', '') for c in cases)}


def drop_privileges():
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)


def check(config):
    reset(config['base_commit'])
    patch = INPUT / 'merged.patch'
    if patch.read_text():
        apply(patch)
    if config.get('judge_test_patch'):
        try:
            apply(INPUT / 'judge.patch', test_patch=True)
        except RuntimeError as exc:
            return {'validinfra': False, 'error': 'immutable test patch failed to apply: ' + str(exc)}
    # The candidate's pytest subprocess cannot write source, tests, git metadata,
    # immutable input assets, or the controller's output directory.
    for parent, dirs, files in os.walk(REPO):
        os.chmod(parent, 0o755)
        for file in files:
            path = Path(parent) / file
            if not path.is_symlink():
                os.chmod(path, 0o755 if os.access(path, os.X_OK) else 0o644)
    os.chmod(REPO / '.git', 0o700)
    work = Path('/tmp/jointverify')
    work.mkdir(mode=0o777)
    os.chmod(work, 0o777)
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(work),
           'TMPDIR': str(work), 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
           'PYTHONPATH': str(REPO / 'src') + ':' + str(REPO),
           'LANG': 'C.UTF-8'}
    xmlpath = work / 'report.xml'
    command = ['python', '-m', 'pytest', '-q', '-o', 'addopts=', '-p', 'no:cacheprovider',
               '-p', 'pytest_mock', '--junitxml=' + str(xmlpath),
               '--basetemp=' + str(work / 'pytest'), *config['test_targets']]
    started = time.monotonic()
    try:
        process = run(command, timeout=config['test_timeout_seconds'], env=env,
                      preexec_fn=drop_privileges, start_new_session=True)
        result = {'validinfra': True, 'pytest_exit_code': process.returncode,
                  'log': process.stdout[-60000:], 'elapsed_seconds': time.monotonic() - started}
    except subprocess.TimeoutExpired as exc:
        return {'validinfra': True, 'passed': False, 'timeout': True,
                'log': str(exc.output or '')[-60000:], 'test_counts': None}
    try:
        result['test_counts'] = counts(xmlpath.read_text())
        result['passed'] = (process.returncode == 0 and result['test_counts']['passed'] > 0
                            and result['test_counts']['failed'] == 0
                            and result['test_counts']['errors'] == 0)
    except (OSError, ET.ParseError) as exc:
        result.update(passed=False, test_counts=None, report_error=str(exc))
    return result


def main():
    config = json.loads((INPUT / 'config.json').read_text())
    try:
        actual = git('rev-parse', 'HEAD')
        if actual != config['base_commit']:
            raise RuntimeError(f'image base mismatch: {actual}')
        result = merge(config) if config['stage'] == 'merge' else check(config)
    except Exception as exc:
        result = {'validinfra': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    (OUTPUT / 'result.json').write_text(json.dumps(result))


if __name__ == '__main__':
    main()

"""Direct evaluation of a declarative artifact on a frozen two-family worker lane.

The GPU lane is prepared, not hardware-validated. This trusted controller fixes
models, workload, resource caps and feedback; scaffold.json cannot change them.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = (('amounts', '.'), ('identity', 'families/identity'))
CALLS = tuple('call-%02d' % i for i in range(6))
SOURCE_AREAS = ('.', 'compute', 'pilot', 'research', 'reference', 'starter', 'tests',
                'families/identity', 'families/identity/reference',
                'families/identity/starter', 'families/identity/tests')
SOURCE_SUFFIXES = {'.py', '.md', '.json'}
TOKEN_FIELDS = ('input_tokens', 'output_tokens', 'total_tokens', 'cached_input_tokens',
                'cache_write_input_tokens', 'reasoning_output_tokens')


class SnapshotError(ValueError):
    pass


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('missing or unsafe JSON artifact')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def constant(unused):
        raise ValueError('nonfinite JSON value')
    value = json.loads(path.read_text(), object_pairs_hook=unique, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError('JSON object required')
    return value


def selected_sources(root):
    """Explicit flat source areas: never recurse into results, caches or weights."""
    root = Path(root)
    files = {}
    for area in SOURCE_AREAS:
        directory = root / area
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            raise SnapshotError('unsafe protected source area: ' + area)
        for path in sorted(directory.iterdir()):
            if path.suffix not in SOURCE_SUFFIXES:
                continue
            if path.is_symlink() or not path.is_file():
                raise SnapshotError('unsafe protected source entry')
            files['contributor-work/livemigrate/' + path.relative_to(root).as_posix()] = path
    relay = root.parent / 'relayrepair/pilot/codex_runner.py'
    if relay.is_symlink() or not relay.is_file():
        raise SnapshotError('missing regular relay transport source')
    files['contributor-work/relayrepair/pilot/codex_runner.py'] = relay
    return files


def source_manifest(root):
    return {name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in selected_sources(root).items()}


def freeze_sources(root, destination):
    """Compare the original read set before/after copying, then verify the copy."""
    before = source_manifest(root)
    for name, path in selected_sources(root).items():
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != before.get(name):
            raise SnapshotError('protected source changed during copy')
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if source_manifest(root) != before:
        raise SnapshotError('protected source changed during copy')
    frozen_root = destination / 'contributor-work/livemigrate'
    verify_snapshot(frozen_root, before)
    return frozen_root, before


def verify_snapshot(root, expected):
    if source_manifest(root) != expected:
        raise SnapshotError('protected snapshot changed')


def worker_profile(path):
    value = read_json(path)
    for key in ('max_model_len', 'max_completion_tokens'):
        if type(value.get(key)) is not int or value[key] <= 0:
            raise ValueError('invalid fixed worker resource cap')
    if value['max_completion_tokens'] > value['max_model_len']:
        raise ValueError('completion reservation exceeds context')
    for key in ('model_id', 'model_revision', 'vllm_version'):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError('invalid fixed worker identity')
    return value


def audit_usage(directory, profile):
    """Retain observed consumption; only six fully attested calls verify caps."""
    paths = {path.name: path for path in directory.iterdir() if path.name.startswith('call-')} \
        if directory.is_dir() else {}
    rows, totals = [], {}
    known, known_entries = 0, 0
    context, completion = profile['max_model_len'], profile['max_completion_tokens']
    for name in sorted(set(CALLS) | set(paths)):
        path, reasons, metadata = paths.get(name), [], {}
        try:
            if path is None or path.is_symlink() or not path.is_dir():
                raise ValueError('missing or unsafe call directory')
            metadata = read_json(path / 'metadata.json')
        except (OSError, ValueError, UnicodeError):
            reasons.append('missing_or_invalid_metadata')
        entries = metadata.get('usage', [])
        valid_entries = isinstance(entries, list) and len(entries) == 1 and isinstance(entries[0], dict)
        numeric = []
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            safe = {key: entry[key] for key in TOKEN_FIELDS
                    if type(entry.get(key)) is int and entry[key] >= 0}
            numeric.append(safe)
            for key, value in safe.items():
                totals[key] = totals.get(key, 0) + value
            if 'input_tokens' in safe and 'output_tokens' in safe:
                known += safe['input_tokens'] + safe['output_tokens']
                known_entries += 1
        usage = entries[0] if valid_entries else {}
        incoming, outgoing, total = (usage.get(key) for key in TOKEN_FIELDS[:3])
        inclusive = all(type(value) is int and value > 0 for value in (incoming, outgoing, total))
        inclusive = inclusive and total == incoming + outgoing
        if not inclusive or not valid_entries:
            reasons.append('incomplete_token_accounting')
        elif incoming + completion > context or outgoing > completion or total > context:
            reasons.append('per_call_token_cap_exceeded')
        for subset, maximum in (('cached_input_tokens', incoming), ('cache_write_input_tokens', incoming),
                                ('reasoning_output_tokens', outgoing)):
            if subset in usage and (type(usage[subset]) is not int or usage[subset] < 0
                                   or type(maximum) is not int or usage[subset] > maximum):
                reasons.append('invalid_token_subset')
        if metadata.get('usage_complete') is not True:
            reasons.append('usage_not_attested_complete')
        if type(metadata.get('generation_requests_started')) is not int or metadata['generation_requests_started'] != 1 \
                or type(metadata.get('automatic_retries')) is not int or metadata['automatic_retries'] != 0:
            reasons.append('generation_count_or_retry_mismatch')
        if metadata.get('model_requested') != profile['model_id'] \
                or metadata.get('model_revision_expected') != profile['model_revision'] \
                or metadata.get('vllm_version') != profile['vllm_version']:
            reasons.append('worker_profile_mismatch')
        if metadata.get('all_generated_token_ids_counted') is not True:
            reasons.append('inclusive_token_ids_not_verified')
        if name not in CALLS:
            reasons.append('unexpected_call')
        rows.append({'call': name, 'observed': path is not None, 'usage': numeric,
                     'bounded_usage_verified': not reasons, 'reasons': reasons})
    verified = set(paths) == set(CALLS) and all(row['bounded_usage_verified'] for row in rows)
    return {'bounded_usage_verified': verified, 'expected_calls': len(CALLS),
            'observed_calls': len(paths), 'calls': rows, 'reported_totals': totals,
            'known_input_plus_output': known if known_entries else None,
            'total_input_plus_output': known if verified else None,
            'cached_input_is_subset_not_added_again': True,
            'reasoning_output_is_subset_not_added_again': True}


def aggregate(reports):
    """Retain every family's diagnostics and consumption, including invalid runs."""
    expected = [name for name, _ in FAMILIES]
    diagnostics, per_family, invalid = {}, {}, []
    for name in expected:
        report = reports.get(name, {})
        heldout = report.get('heldout', {})
        heldout = heldout if isinstance(heldout, dict) else {}
        cases = heldout.get('cases', [])
        usage = report.get('accounting', {})
        diagnostics[name] = {'status': report.get('status', 'not_run'),
                             'generation_completed': report.get('generation_completed', False),
                             'infrastructure_affected': report.get('infrastructure_affected'),
                             'passed': heldout.get('passed'), 'total': heldout.get('total'),
                             'usage': usage, 'pilot_reported_usage': report.get('usage')}
        case_valid = isinstance(cases, list) and len(cases) == 3 \
            and all(isinstance(case, dict) and isinstance(case.get('name'), str)
                    and case.get('status') == 'scored' and type(case.get('passed')) is bool for case in cases)
        case_valid = case_valid and len({case['name'] for case in cases}) == 3
        if report.get('status') != 'scored' or report.get('generation_completed') is not True \
                or report.get('infrastructure_affected') is not False or report.get('calls') != 6 \
                or report.get('process_exit_code', 0) != 0 or heldout.get('status') != 'scored' \
                or heldout.get('total') != 3 or not case_valid or usage.get('bounded_usage_verified') is not True:
            invalid.append(name)
        else:
            per_family[name] = sum(case['passed'] for case in cases) / 3
    verified = all(diagnostics[name]['usage'].get('bounded_usage_verified') is True for name in expected)
    known = [diagnostics[name]['usage'].get('known_input_plus_output') for name in expected]
    known = [value for value in known if type(value) is int]
    result = {'status': 'scored', 'score': None, 'families': diagnostics,
              'bounded_usage_verified': verified,
              'accounted_consumption': {'known_input_plus_output': sum(known) if known else None,
                                       'total_input_plus_output': sum(known) if verified else None,
                                       'complete': verified},
              'scope': 'two public semantic families; no claim of unseen-family transfer'}
    if set(reports) != set(expected) or invalid:
        result.update(status='unscored', reason='invalid_or_incomplete_family', invalid_families=invalid)
    else:
        result.update(score=sum(per_family.values()) / len(per_family),
                      metric='macro_family_history_safe_trace_fraction', family_scores=per_family)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--scaffold', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(argv)
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        ap.error('Use a fresh output directory outside the source tree')
    output.mkdir(parents=True, exist_ok=False)
    reports, snapshot_error = {}, None
    provenance = {'calls_per_family': 6, 'families': [name for name, _ in FAMILIES]}
    profile = None
    try:
        frozen_root, manifest = freeze_sources(ROOT, output / 'frozen')
        write_json(output / 'protected-source-manifest.json', manifest)
        spec = importlib.util.spec_from_file_location('research_policy_validation', frozen_root / 'pilot/scaffold.py')
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        policy = validator.load(args.scaffold)
        frozen_scaffold = output / 'scaffold.json'
        write_json(frozen_scaffold, policy)
        profile_path = frozen_root / 'compute/qwen38.json'
        profile = worker_profile(profile_path)
        provenance.update(scaffold_sha256=hashlib.sha256(frozen_scaffold.read_bytes()).hexdigest(),
                          model_profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),
                          model_profile=profile, max_inclusive_input_output_tokens=2 * 6 * profile['max_model_len'])
        write_json(output / 'provenance.json', provenance)
        for name, relative_root in FAMILIES:
            try:
                verify_snapshot(frozen_root, manifest)
                if hashlib.sha256(frozen_scaffold.read_bytes()).hexdigest() != provenance['scaffold_sha256']:
                    raise SnapshotError('frozen scaffold changed')
            except (OSError, ValueError) as exc:
                snapshot_error = type(exc).__name__
                break  # Changed controller is not executed; remaining family is explicitly not_run.
            destination = output / name
            command = [sys.executable, str(frozen_root / 'pilot/run.py'), '--mode', 'team',
                       '--scaffold', str(frozen_scaffold), '--task-root', str(frozen_root / relative_root),
                       '--output', str(destination), '--inference-timeout', '1800',
                       '--adapter-command', sys.executable, str(frozen_root / 'pilot/compatible_adapter.py'), str(profile_path)]
            report = {'status': 'incomplete'}
            with (output / (name + '.stdout.local.txt')).open('w') as stdout, \
                 (output / (name + '.stderr.local.txt')).open('w') as stderr:
                try:
                    process = subprocess.run(command, stdout=stdout, stderr=stderr)
                    path = destination / 'summary.json'
                    if not path.exists():
                        path = destination / 'failure.json'
                    report = read_json(path)
                    report['process_exit_code'] = process.returncode
                except (OSError, ValueError, UnicodeError) as exc:
                    report['artifact_error_type'] = type(exc).__name__
            reports[name] = report
        verify_snapshot(frozen_root, manifest)
        if hashlib.sha256(frozen_scaffold.read_bytes()).hexdigest() != provenance['scaffold_sha256']:
            raise SnapshotError('frozen scaffold changed')
    except (OSError, ValueError, UnicodeError, KeyError, TypeError) as exc:
        snapshot_error = type(exc).__name__
    # Always inspect observed calls, even when a source change invalidates scoring.
    if profile is not None:
        for name, _ in FAMILIES:
            reports.setdefault(name, {'status': 'not_run'})['accounting'] = audit_usage(output / name, profile)
    result = aggregate(reports)
    result['source_snapshot_verified'] = snapshot_error is None
    result['scaffold_sha256'] = provenance.get('scaffold_sha256')
    if snapshot_error is not None:
        result.update(status='unscored', score=None, reason='protected_source_or_artifact_changed_or_invalid',
                      snapshot_error_type=snapshot_error)
        result.pop('family_scores', None)
    write_json(output / 'result.json', result)
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()

"""Export an allowlisted pilot result and candidate sources, never raw call logs.

Usage: python3 pilot/export_result.py --run RUN --output NEW_DIRECTORY
       --source-revision FULL_GIT_COMMIT
Only finished local runs should be exported. No candidate code is executed.
Candidate source still needs review for secrets/PII; absolute-path detection is
not a general privacy scrubber and never rewrites the submitted code.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tokenize

ROLES = ('db', 'api', 'consumer')
TOKENS = ('input_tokens', 'output_tokens', 'cached_input_tokens',
          'cache_write_input_tokens', 'reasoning_output_tokens', 'total_tokens')
INFRASTRUCTURE = {'check_error', 'infrastructure_or_incomplete', 'infrastructure_error'}
ABSOLUTE = re.compile(r'''(?:^|[\s"'`(=:<>])(?:/(?!/)[A-Za-z_.~][^\s"'`<>)]*|[A-Za-z]:[\\/][^\s"'`<>)]*)''')
LABEL = re.compile(r'[A-Za-z0-9_.:+-]{1,160}\Z')
IDENTIFIER = re.compile(r'[A-Za-z0-9_./:+-]{1,256}\Z')


class ExportError(ValueError):
    pass


def read_json(path):
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ExportError('invalid local JSON artifact: ' + path.name)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    try:
        result = json.loads(path.read_text(), object_pairs_hook=unique,
                            parse_constant=lambda unused: (_ for _ in ()).throw(ValueError('nonfinite')))
    except (ValueError, UnicodeError):
        return None  # An interrupted artifact is unknown, never a zero score.
    return result if isinstance(result, dict) else None


def label(value, identifier=False):
    pattern = IDENTIFIER if identifier else LABEL
    if not isinstance(value, str) or not pattern.fullmatch(value):
        return None
    if value.startswith(('/', '\\')) or '://' in value or re.match(r'^[A-Za-z]:', value):
        return None
    return value


def scalar_fields(source, names):
    result = {}
    for name in names:
        if name not in source:
            continue
        value = source[name]
        if value is None or type(value) in (bool, int, float):
            result[name] = value
        elif (safe := label(value)) is not None:
            result[name] = safe
    return result


def violations(items):
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            result.append({'code': 'unavailable_violation_details'})
            continue
        safe = scalar_fields(item, ('code', 'step', 'action', 'actor', 'operation', 'error_type', 'effect_count'))
        safe['details_omitted'] = any(key not in safe for key in item)
        result.append(safe)
    return result


def counts(source, names):
    """Fixed-name nonnegative counters, never arbitrary strings or booleans."""
    return {name: source[name] for name in names
            if type(source.get(name)) is int and source[name] >= 0}


def outcome(raw, suite=None):
    if not isinstance(raw, dict):
        return {'status': 'not_recorded', 'suite': suite, 'score': None}
    clean = scalar_fields(raw, ('status', 'suite', 'passed', 'total', 'score', 'exit_code', 'seconds', 'error'))
    clean.setdefault('status', 'unknown')
    if suite is not None:
        clean.setdefault('suite', suite)
    if isinstance(raw.get('cases'), list):
        clean['cases'] = []
        for case in raw['cases']:
            if not isinstance(case, dict):
                clean['cases'].append({'status': 'unknown', 'score': None})
                continue
            row = scalar_fields(case, ('name', 'status', 'passed', 'score'))
            for component in ('static', 'trace'):
                if isinstance(case.get(component), dict):
                    row[component] = scalar_fields(case[component],
                        ('passed', 'accepted_payments', 'accepted_operations', 'physical_effects'))
                    row[component].update(counts(case[component],
                        ('violation_count', 'physical_fulfillments')))
                    row[component]['violations'] = violations(case[component].get('violations', []))
            if isinstance(case.get('completion'), dict):
                row['completion'] = scalar_fields(case['completion'],
                    ('passed', 'expanded', 'contracted', 'completed_steps', 'total_steps',
                     'candidate_callbacks', 'deliveries'))
                row['completion'].update(counts(case['completion'],
                    ('resolved_calls', 'total_calls', 'fair_rounds', 'queued_messages')))
            if isinstance(case.get('history'), dict):
                history = case['history']
                row['history'] = counts(history, ('explored',))
                row['history'].update({key: history[key] for key in ('passed', 'exhaustive')
                                       if type(history.get(key)) is bool})
                if history.get('reason') in ('linearizable', 'not_linearizable', 'incomplete_history',
                                              'invalid_history', 'bound_exhausted'):
                    row['history']['reason'] = history['reason']
            if isinstance(case.get('faults'), dict):
                faults = case['faults']
                row['faults'] = counts(faults, ('replayed_packets',))
                row['faults'].update({key: faults[key] for key in ('lost_output', 'lost_effect_ack')
                                     if type(faults.get(key)) is bool})
                trigger = faults.get('lost_output_trigger')
                if trigger is None:
                    row['faults']['lost_output_trigger'] = None
                elif isinstance(trigger, dict):
                    safe_trigger = counts(trigger, ('step',))
                    for key, options in (('node', ('source', 'gateway', 'A', 'B')),
                                         ('input_kind', ('init', 'client', 'move', 'tick', 'reply_ack')),
                                         ('sku', ('X', 'Y', 'Z'))):
                        if trigger.get(key) in options:
                            safe_trigger[key] = trigger[key]
                    row['faults']['lost_output_trigger'] = safe_trigger
            clean['cases'].append(row)
    return clean


def safe_hashes(raw):
    if raw is None:
        return {}
    result = {}
    for name, digest in raw.items():
        if (not isinstance(name, str) or PurePosixPath(name).is_absolute()
                or '\\' in name or ':' in name or '\n' in name or '\r' in name
                or not re.fullmatch(r'[A-Za-z0-9_./-]+', name)
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ExportError('source hashes contain an unsafe path or invalid digest')
        result[name] = digest
    return result


def call_metadata(run):
    calls = []
    paths = sorted((p for p in run.iterdir() if re.fullmatch(r'call-[0-9]+', p.name)),
                   key=lambda p: int(p.name.split('-')[1]))
    for path in paths:
        if path.is_symlink() or not path.is_dir():
            raise ExportError('call artifact must be a regular directory')
        raw = read_json(path / 'metadata.json')
        row = {'index': int(path.name.split('-')[1]), 'metadata_available': raw is not None}
        raw = raw or {}
        row.update(scalar_fields(raw, ('status', 'seconds', 'return_code', 'tool_free',
                   'usage_complete', 'usage_reported_complete', 'generation_requests_started',
                   'automatic_retries', 'all_generated_token_ids_counted', 'error_type')))
        for name in ('model_requested', 'model_revision_expected', 'reasoning_effort', 'vllm_version', 'model_selection_source'):
            row[name] = label(raw.get(name), identifier=True)
        row['usage'] = []
        entries = raw.get('usage', [])
        valid = isinstance(entries, list) and bool(entries)
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                valid = False
                continue
            safe = {key: entry[key] for key in TOKENS if type(entry.get(key)) is int and entry[key] >= 0}
            complete = 'input_tokens' in safe and 'output_tokens' in safe
            if complete:
                complete &= safe.get('cached_input_tokens', 0) <= safe['input_tokens']
                complete &= safe.get('reasoning_output_tokens', 0) <= safe['output_tokens']
                complete &= safe.get('total_tokens', safe['input_tokens'] + safe['output_tokens']) == safe['input_tokens'] + safe['output_tokens']
            valid &= complete
            row['usage'].append(safe)
        cli_complete = (raw.get('status') == 'completed' and raw.get('tool_free') is True
                        and type(raw.get('return_code')) is int and raw['return_code'] == 0)
        explicit_complete = raw.get('usage_complete') is True
        row['usage_evidence'] = ('adapter_complete_flag' if explicit_complete else
                                 'completed_tool_free_cli_record' if cli_complete else
                                 'unverified_reported_counts')
        row['usage_known'] = bool(valid and raw.get('usage_complete') is not False
                                 and (explicit_complete or cli_complete))
        if isinstance(raw.get('raw_reported_usage'), dict):
            row['raw_reported_usage'] = {key: value for key, value in raw['raw_reported_usage'].items()
                if key in ('prompt_tokens', 'completion_tokens', 'total_tokens') and type(value) is int and value >= 0}
        calls.append(row)
    return calls


def usage_summary(calls, summary):
    totals = {}
    for call in calls:
        for entry in call['usage']:
            for key, value in entry.items():
                totals[key] = totals.get(key, 0) + value
    known = sum(entry['input_tokens'] + entry['output_tokens'] for call in calls for entry in call['usage']
                if 'input_tokens' in entry and 'output_tokens' in entry)
    complete_calls = sum(call['usage_known'] for call in calls)
    counts_match = (type(summary.get('calls')) is int and summary['calls'] == len(calls)
                    and [call['index'] for call in calls] == list(range(summary['calls'])))
    reported = summary.get('usage', {}).get('reported_totals', {}) if isinstance(summary.get('usage'), dict) else {}
    comparable = {key: value for key, value in reported.items() if key in TOKENS} if isinstance(reported, dict) else {}
    totals_match = all(totals.get(key) == value for key, value in comparable.items()) if comparable else None
    complete = bool(calls and counts_match and complete_calls == len(calls) and totals_match is not False)
    return {'complete': complete, 'complete_for_observed_calls': bool(calls and complete_calls == len(calls)),
            'observed_calls': len(calls), 'calls_with_complete_usage': complete_calls,
            'calls_with_unknown_usage': len(calls) - complete_calls,
            'reported_call_count_verified': counts_match, 'summary_totals_match': totals_match,
            'reported_totals': totals, 'known_input_plus_output': known if totals else None,
            'total_input_plus_output': known if complete else None,
            'cached_input_is_subset_not_added_again': True,
            'reasoning_output_is_subset_not_added_again': True}


def candidate_sources(run, summary):
    directories = sorted((p for p in run.iterdir() if re.fullmatch(r'candidate-[0-9]+', p.name)),
                         key=lambda p: int(p.name.split('-')[1]), reverse=True)
    frozen = read_json(run / 'candidate-sha256.json')
    summary_hashes = summary.get('candidate_sha256')
    if frozen is not None and summary_hashes is not None and frozen != summary_hashes:
        raise ExportError('candidate hash artifacts disagree')
    frozen = frozen if frozen is not None else summary_hashes
    for directory in directories:
        if directory.is_symlink() or not directory.is_dir():
            raise ExportError('candidate artifact must be a regular directory')
        if not all((directory / (role + '.py')).is_file() for role in ROLES):
            continue
        files, hashes = {}, {}
        for role in ROLES:
            path = directory / (role + '.py')
            if path.is_symlink() or path.stat().st_size > 1024 * 1024:
                raise ExportError('candidate ' + role + '.py is not an eligible regular source file')
            data = path.read_bytes()
            try:
                source = data.decode('utf-8')
            except UnicodeError:
                raise ExportError('candidate ' + role + '.py is not UTF-8')
            candidates = [(source, 1)]
            try:
                for token in tokenize.generate_tokens(io.StringIO(source).readline):
                    if token.type == tokenize.STRING:
                        try:
                            value = ast.literal_eval(token.string)
                        except (ValueError, SyntaxError):
                            continue
                        if isinstance(value, str):
                            candidates.append((value, token.start[0]))
            except (tokenize.TokenError, IndentationError):
                pass  # Invalid source is still reproducible; scan its raw text.
            for value, line in candidates:
                found = ABSOLUTE.search(value)
                if found:
                    line += value[:found.start()].count('\n')
                    raise ExportError('candidate ' + role + '.py contains an absolute filesystem path near line ' + str(line) + '; no export written')
            files[role + '.py'] = data
            hashes[role] = hashlib.sha256(data).hexdigest()
        if frozen is not None and frozen != hashes:
            raise ExportError('candidate source does not match recorded final hashes')
        stage = int(directory.name.split('-')[1])
        return {'available': True, 'stage': stage, 'is_final': frozen is not None,
                'sha256': hashes, 'recorded_hashes_verified': frozen is not None}, files
    return {'available': False, 'stage': None, 'is_final': False, 'sha256': None,
            'recorded_hashes_verified': False}, {}


def prepare(run, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ExportError('--source-revision must be the full 40-character Git commit')
    summary = read_json(run / 'summary.json') or {}
    failure = read_json(run / 'failure.json') or {}
    if not summary and not failure:
        raise ExportError('run has no readable summary.json or failure.json; may still be active')
    hashes_raw = read_json(run / 'source-sha256.json')
    hashes = safe_hashes(hashes_raw)
    calls = call_metadata(run)
    metadata_models = sorted({row['model_requested'] for row in calls if row['model_requested']})
    metadata_efforts = sorted({row['reasoning_effort'] for row in calls if row['reasoning_effort']})
    metadata_selections = sorted({row['model_selection_source'] for row in calls if row['model_selection_source']})
    record = summary or failure
    requested = label(record.get('requested_model'), identifier=True)
    effort = label(record.get('reasoning_effort'))
    selection = label(record.get('model_selection_source'))
    if selection is None and len(metadata_selections) == 1:
        selection = metadata_selections[0]
    if requested in (None, 'external_adapter'):
        requested = metadata_models[0] if len(metadata_models) == 1 else None
    if effort in (None, 'adapter_declared'):
        effort = metadata_efforts[0] if len(metadata_efforts) == 1 else None
    public = []
    recorded_public = summary.get('public', []) if isinstance(summary.get('public'), list) else []
    public_files = {int(p.stem.split('-')[1]): p for p in run.glob('public-*.json') if re.fullmatch(r'public-[0-9]+', p.stem)}
    stages = sorted(set(range(len(recorded_public))) | set(public_files))
    for stage in stages:
        raw = recorded_public[stage] if stage < len(recorded_public) else read_json(public_files[stage])
        public.append({'stage': stage, 'outcome': outcome(raw, 'public')})
    heldout = outcome(summary.get('heldout') if isinstance(summary.get('heldout'), dict) else read_json(run / 'heldout.json'), 'heldout')
    candidate, files = candidate_sources(run, summary)
    statuses = [item['outcome']['status'] for item in public] + [heldout['status']]
    case_statuses = [case.get('status') for report in [item['outcome'] for item in public] + [heldout]
                     for case in report.get('cases', [])]
    coverage = len(public) == 2 and all(status != 'not_recorded' for status in statuses)
    infrastructure = (True if record.get('infrastructure_affected') is True or any(status in INFRASTRUCTURE for status in statuses)
                      else False if summary and coverage else None)
    result = {
        'schema_version': 1, 'source_revision': revision, 'source_revision_source': 'operator_supplied',
        'source_hashes_available': hashes_raw is not None,
        'run': scalar_fields(summary or failure, ('status', 'generation_completed', 'mode', 'calls', 'seconds',
                             'inference_timeout_seconds', 'check_timeout_seconds')),
        'model': {'requested_identifier': requested, 'reasoning_effort': effort,
                  'model_selection_source': selection, 'metadata_selection_sources': metadata_selections,
                  'metadata_identifiers': metadata_models, 'metadata_efforts': metadata_efforts,
                  'identity_consistent': len(metadata_models) <= 1 and (not metadata_models or requested in metadata_models),
                  'immutable_revision_expected': sorted({row['model_revision_expected'] for row in calls if row['model_revision_expected']}),
                  'server_weight_attestation': 'not_provided'},
        'validity': {'generation_completed': summary.get('generation_completed') if type(summary.get('generation_completed')) is bool else None,
                     'failure_recorded': bool(failure), 'failure_type': label(failure.get('error')),
                     'failure_category': label(failure.get('failure_category')),
                     'infrastructure_affected': infrastructure,
                     'check_coverage_complete': coverage,
                     'candidate_invalid': any(status == 'candidate_invalid' for status in statuses + case_statuses),
                     'source_hashes_verified_against_git': False},
        'public': public, 'heldout': heldout, 'usage': usage_summary(calls, summary),
        'calls': calls, 'candidate': candidate,
        'candidate_source_review': 'Absolute-path scan only; separate secrets/PII review required before publication.',
        'scope': 'Schedules within a family are correlated stress cases, not independent tasks.',
    }
    result['run'].setdefault('status', 'incomplete')
    if isinstance(record.get('scaffold_sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', record['scaffold_sha256']):
        result['run']['scaffold_sha256'] = record['scaffold_sha256']
    return result, hashes, files


def export(run, output, revision):
    run, output = Path(run).resolve(), Path(output).absolute()
    if output == run or run in output.resolve().parents:
        raise ExportError('export destination must be outside the original run')
    if output.exists() or output.is_symlink():
        raise ExportError('export destination already exists; refusing to overwrite')
    result, hashes, files = prepare(run, revision)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    (output / 'source-sha256.json').write_text(json.dumps(hashes, indent=2, sort_keys=True) + '\n')
    if files:
        (output / 'candidate').mkdir()
        for name, data in files.items():
            (output / 'candidate' / name).write_bytes(data)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args(argv)
    try:
        result = export(args.run, args.output, args.source_revision)
    except ExportError as exc:
        parser.exit(2, str(exc) + '\n')
    print(json.dumps({'exported': True, 'status': result['run']['status'],
                      'usage_complete': result['usage']['complete'],
                      'candidate_available': result['candidate']['available']}))


if __name__ == '__main__':
    main()

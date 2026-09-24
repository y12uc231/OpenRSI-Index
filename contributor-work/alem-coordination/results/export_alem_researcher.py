"""Export exact generated sources and allowlisted evidence; never import candidates.

Requires a finished pilot summary. Reads neither prompts nor raw model events,
reasoning, stderr, nor launcher commands. Output must be a new directory.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
import re
import statistics
import subprocess
from pathlib import Path

COMMIT = 'd4bdd34f4170d2e61f24527d7ed68b3ad0866492'
TASK = 'contributor-work/alem-coordination'
PRIMARY = 'Team/coord_reward_pct_of_max'
METRICS = tuple('Team/' + k for k in ('coord_reward_pct_of_max', 'normal_reward_pct_of_max', 'reward_pct_of_max', 'soft_coord_reward_pct_of_max', 'sync_hard_coord_reward_pct_of_max', 'handover_coord_reward_pct_of_max', 'construction_coord_reward_pct_of_max'))
DIAGNOSTICS = ('Cooperation/alive_agent_steps', 'Cooperation/actionable_agent_steps', 'Deaths/total_deaths', 'Deaths/dehydration_count', 'Deaths/starvation_count', 'Deaths/exhaustion_count', 'Deaths/mob_combat_count', 'Deaths/friendly_fire_count', 'Progression/max_level_reached', 'Coordination/sync_attempts', 'Coordination/sync_successes', 'Coordination/coord_sync_success_rate', 'Coordination/mine_sync_hard', 'Coordination/mine_sync_soft', 'Coordination/handover_setups', 'Coordination/handover_successes', 'Coordination/handover_expiries', 'Coordination/construction_attempts', 'Coordination/construction_successes', 'Coordination/elite_attempts', 'Coordination/elite_successes', 'Communication/total_comm_count')
COSTS = ('steps', 'seconds', 'ipc_seconds', 'overrides', 'action_count', 'policy_forward_batches', 'controller_calls', 'native_communication_actions')
SUITES = {'dev': list(range(20000, 20004)), 'evaluation': list(range(9999, 10019))}
STATUSES = {'scored', 'candidate_invalid', 'infrastructure_or_incomplete'}
TOKENS = ('input_tokens', 'output_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'reasoning_output_tokens', 'total_tokens')
PRIVATE = re.compile(r'/Users/|/home/|/var/folders/|/private/var/|(?:sk-proj-|gh[pousr]_)[A-Za-z0-9]{12,}')
HEX = re.compile(r'^[0-9a-f]{64}$')


def sha(raw): return hashlib.sha256(raw).hexdigest()
def finite(x): return type(x) in (int, float) and math.isfinite(x)
def close(a, b): return finite(a) and finite(b) and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)
def number(x): return x if finite(x) else None

def code(x):
    return x if isinstance(x, str) and re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,79}', x) else 'other'


def json_bytes(value): return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


class Reader:
    def __init__(self, root): self.root, self.reads = root.resolve(), {}
    def raw(self, name):
        path = self.root / name
        if path.is_symlink() or not path.resolve().is_relative_to(self.root) or not path.is_file():
            raise ValueError('Not a regular input: ' + name)
        for parent in path.parents:
            if parent == self.root: break
            if parent.is_symlink(): raise ValueError('Symlink parent')
        raw = path.read_bytes()
        self.reads[name] = sha(raw)
        return raw
    def obj(self, name): return json.loads(self.raw(name))
    def exists(self, name): return (self.root / name).is_file()
    def verify(self):
        if any(sha((self.root / name).read_bytes()) != expected for name, expected in self.reads.items()):
            raise ValueError('Input changed during export')


class Frozen:
    def __init__(self, repo): self.repo, self.cache = repo, {}
    def raw(self, path):
        # Git object reads only; never executes files from the commit.
        if path not in self.cache:
            self.cache[path] = subprocess.check_output(['git', 'show', COMMIT + ':' + path], cwd=self.repo)
        return self.cache[path]
    def obj(self, path): return json.loads(self.raw(path))
    def source_map(self, given):
        expected = {}
        # Resolve only the source paths the frozen pilot actually records.
        allowed_external = {'../relayrepair/pilot/codex_runner.py', '../livemigrate/pilot/compatible_adapter.py', '../livemigrate/compute/qwen38.json'}
        for name, digest in given.items():
            if name in allowed_external:
                path = 'contributor-work/' + name[3:]
            elif not Path(name).is_absolute() and '..' not in Path(name).parts:
                path = TASK + '/' + name
            else: raise ValueError('Unsafe recorded source path')
            if not HEX.fullmatch(str(digest)): raise ValueError('Invalid source digest')
            expected[name] = sha(self.raw(path))
        mandatory = {'TASK_DESIGN.md', 'pilot/PROTOCOL.md', 'pilot/run.py', 'controller/engine.py', 'controller/launcher.py', 'controller/controller_driver.py', 'controller/wire.py', 'controller/feedback.py', 'controller/CONTRACT.md', 'baseline/source-manifest.json', 'baseline/asset-manifest.json'} | allowed_external
        return given == expected and mandatory <= given.keys()


def metadata(value, requested):
    records = value.get('usage', [])
    usage = [{k: r[k] for k in TOKENS if type(r.get(k)) is int and r[k] >= 0} for r in records if isinstance(r, dict)] if isinstance(records, list) else []
    valid = (value.get('status') == 'completed' and value.get('return_code') == 0 and value.get('tool_free') is True
             and value.get('model_requested') == requested and value.get('reasoning_effort') == 'ultra' and len(usage) == 1
             and all(k in usage[0] for k in ('input_tokens', 'output_tokens')))
    return {'status': value.get('status') if value.get('status') in ('completed', 'invalid', 'timeout') else 'other',
            'model_requested': requested, 'reasoning_effort': 'ultra', 'model_identity': 'requested provider alias; immutable server snapshot not exposed',
            'seconds': number(value.get('seconds')), 'return_code': value.get('return_code') if type(value.get('return_code')) is int else None,
            'tool_free': value.get('tool_free') is True, 'usage': usage, 'complete_call_evidence': valid}


def sanitize_result(value, suite, candidate_hash, frozen):
    expected = SUITES[suite]
    problems = []
    host = value.get('host_provenance', {})
    hashes = host.get('hashes', {})
    provenance = value.get('provenance_verified') is True and host.get('source_candidate_unchanged') is True
    source = frozen.obj(TASK + '/baseline/source-manifest.json')
    assets = frozen.obj(TASK + '/baseline/asset-manifest.json')
    wanted_assets = {r['path'].removeprefix('assets/'): r['sha256'] for r in assets['files']}
    if hashes.get('source_revision') != source['revision'] or hashes.get('source_sha256') != source['files']:
        problems.append('environment_source_provenance_mismatch')
    if hashes.get('asset_revision') != assets['revision'] or hashes.get('asset_sha256') != wanted_assets:
        problems.append('policy_asset_provenance_mismatch')
    if hashes.get('candidate_sha256') != candidate_hash: problems.append('candidate_hash_mismatch')
    wanted_runner = {k: sha(frozen.raw(TASK + '/controller/' + k)) for k in ('launcher.py', 'controller_driver.py', 'wire.py', 'engine.py', 'feedback.py', 'CONTRACT.md')}
    if hashes.get('runner_sha256') != wanted_runner: problems.append('runner_hash_mismatch')
    wanted_manifests = {k: sha(frozen.raw(TASK + '/baseline/' + k)) for k in ('source-manifest.json', 'asset-manifest.json')}
    if hashes.get('manifest_sha256') != wanted_manifests: problems.append('manifest_hash_mismatch')
    if value.get('suite') != suite or value.get('world_ids') != expected or value.get('total') != len(expected): problems.append('suite_denominator_mismatch')
    pinned_baseline = frozen.obj(TASK + '/controller/evidence/evaluation-baseline.json')
    if host.get('environment_image') != pinned_baseline['environment_image'] or host.get('worker_image') != pinned_baseline['worker_image']:
        problems.append('container_image_mismatch')
    cases = value.get('cases', [])
    if [c.get('world_id') for c in cases] != expected: problems.append('world_inventory_mismatch')
    rows = []
    for case in cases:
        row = {'world_id': case.get('world_id') if type(case.get('world_id')) is int else None,
               'status': case.get('status') if case.get('status') in STATUSES else 'infrastructure_or_incomplete',
               'naturally_terminated': case.get('naturally_terminated') is True,
               'diagnostic_code': None if case.get('diagnostic_code') is None else code(case['diagnostic_code']),
               'error_type': None if case.get('error_type') is None else code(case['error_type']),
               'reward_fraction': {k: v for k, v in case.get('metrics', {}).items() if k in METRICS and finite(v)},
               'native_diagnostics': {k: v for k, v in case.get('metrics', {}).items() if k in DIAGNOSTICS and finite(v)},
               'costs': {k: number(case.get(k)) for k in COSTS},
               'trace_sha256': case.get('trace_sha256') if HEX.fullmatch(str(case.get('trace_sha256'))) else None}
        if row['status'] == 'scored' and (PRIMARY not in row['reward_fraction'] or not 0 <= row['reward_fraction'][PRIMARY] <= 1):
            problems.append('invalid_world_metric')
        rows.append(row)
    scored = sum(r['status'] == 'scored' for r in rows)
    full = (len(rows) == len(expected) and scored == len(expected) and all(PRIMARY in r['reward_fraction'] for r in rows))
    measured = statistics.mean(r['reward_fraction'][PRIMARY] for r in rows) if full else None
    if full and (not close(measured, value.get('primary_score')) or value.get('scored') != scored): problems.append('score_aggregation_mismatch')
    valid = (provenance and not problems and value.get('status') == 'scored' and value.get('infrastructure_affected') is False and full)
    score = measured if valid else None
    counts = dict(collections.Counter(r['status'] for r in rows))
    aggregate = {k: sum(r['costs'][k] for r in rows if finite(r['costs'][k])) for k in COSTS}
    metrics = {k: statistics.mean(r['reward_fraction'][k] for r in rows) for k in METRICS if rows and all(k in r['reward_fraction'] for r in rows)} if valid else {}
    for k, v in metrics.items():
        if not close(v, value.get('metrics_mean', {}).get(k)): problems.append('secondary_aggregation_mismatch')
    if problems: score, metrics, valid = None, {}, False
    feedback = {'status': 'scored' if valid else 'unscored', 'total': len(expected), 'scored': scored,
                'primary_score': score, 'metrics_mean': metrics, 'validity_counts': counts,
                'diagnostic_counts': dict(collections.Counter(r['diagnostic_code'] or 'other' for r in rows if r['status'] != 'scored')),
                'error_type_counts': dict(collections.Counter(r['error_type'] or 'other' for r in rows if r['status'] != 'scored')),
                'aggregate_costs': {k: aggregate[k] for k in ('steps', 'seconds', 'ipc_seconds', 'overrides', 'action_count', 'native_communication_actions')},
                'override_fraction': aggregate['overrides']/aggregate['action_count'] if aggregate['action_count'] else 0.,
                'provenance_verified': provenance and not problems,
                'infrastructure_affected': value.get('infrastructure_affected') is True, 'llm_calls': 0}
    result = {'suite': suite, 'status': feedback['status'], 'expected_world_ids': expected, 'total': len(expected), 'scored': scored,
              'primary_score_fraction': score, 'reward_fraction_mean': metrics, 'aggregate_costs': aggregate,
              'native_diagnostics_mean': {k: statistics.mean(r['native_diagnostics'][k] for r in rows) for k in DIAGNOSTICS if rows and all(k in r['native_diagnostics'] for r in rows)},
              'worlds': rows, 'audit_problems': sorted(set(problems)), 'provenance_verified': provenance and not problems,
              'infrastructure_affected': value.get('infrastructure_affected') is True,
              'candidate_sha256': candidate_hash, 'source_sha': source['revision'], 'weights_revision': assets['revision'],
              'runner_sha256': wanted_runner, 'manifest_sha256': wanted_manifests,
              'environment_image': host.get('environment_image') if re.fullmatch(r'sha256:[0-9a-f]{64}', str(host.get('environment_image'))) else None,
              'worker_image': host.get('worker_image') if re.fullmatch(r'python@sha256:[0-9a-f]{64}', str(host.get('worker_image'))) else None,
              'operator_timeout_seconds': number(host.get('operator_timeout_seconds')),
              'host_wall_seconds': number(host.get('wall_seconds')), 'python_wall_seconds': number(value.get('python_wall_seconds')),
              'compile_warmup_seconds': number(value.get('compile_warmup_seconds')), 'peak_engine_rss_kib_linux': number(value.get('peak_rss_kib_linux'))}
    if valid:
        scores = [r['reward_fraction'][PRIMARY] for r in rows]
        result['world_score_distribution'] = {'sample_sd_fraction': statistics.stdev(scores), 'min_fraction': min(scores), 'max_fraction': max(scores)}
    return result, feedback


def export(run, repo, output):
    reader, frozen = Reader(run), Frozen(repo)
    if output.exists(): raise ValueError('Refusing existing output directory')
    summary = reader.obj('summary.json')
    requested = summary.get('model_requested')
    if requested not in ('gpt-6-astra', 'gpt-6-sol'): raise ValueError('Unrecognized declared arm')
    if summary.get('status') == 'running': raise ValueError('Run is still active')
    sources = reader.obj('source-sha256.json')
    source_ok = frozen.source_map(sources) and summary.get('source_git_commit') == COMMIT and summary.get('source_unchanged') is True
    study = frozen.obj(TASK + '/pilot/STUDY.json')
    packet = reader.obj('packet-manifest.json')
    packet_ok = packet == study['public_packet_files']
    baseline_ok = (summary.get('matched_baseline_sha256') == study['matched_baseline_result_sha256'] and close(summary.get('matched_baseline_primary_score'), study['matched_baseline_score']))
    files, generations, combined_usage = {}, [], collections.Counter()
    audits = []
    inventories = {}
    for prefix in ('call', 'check', 'candidate'):
        expected = {f'{prefix}-{index:02d}' for index in range(3)}
        entries = {path.name: path for path in run.iterdir() if path.name.startswith(prefix + '-')}
        inventories[prefix] = entries
        if set(entries) != expected or any(not path.is_dir() or path.is_symlink() for path in entries.values()):
            audits.append(prefix + '_directory_inventory_mismatch')
    extra_calls, extra_usage = [], collections.Counter()
    for name in sorted(set(inventories['call']) - {'call-00', 'call-01', 'call-02'}):
        # Only metadata is read. Never execute or open an extra call's prompts,
        # events, notes or controller, and never publish arbitrary path names.
        extra = {'call': name if re.fullmatch(r'call-[0-9]{2,6}', name) else 'other_call_entry'}
        if reader.exists(name + '/metadata.json'):
            try:
                extra['inference'] = metadata(reader.obj(name + '/metadata.json'), requested)
                for record in extra['inference']['usage']:
                    extra_usage.update(record)
                if not extra['inference']['complete_call_evidence']:
                    extra['diagnostic_code'] = 'incomplete_extra_call_evidence'
            except (OSError, ValueError, TypeError, AttributeError):
                extra['diagnostic_code'] = 'unreadable_extra_call_metadata'
        else:
            extra['diagnostic_code'] = 'missing_extra_call_metadata'
        extra_calls.append(extra)
    combined_usage.update(extra_usage)
    for index in range(3):
        c = f'call-{index:02d}'
        row = {'generation': index + 1, 'attempted': (run / c).is_dir(), 'artifact_available': False}
        if reader.exists(c + '/metadata.json'):
            row['inference'] = metadata(reader.obj(c + '/metadata.json'), requested)
            for record in row['inference']['usage']: combined_usage.update(record)
        if reader.exists(c + '/response.json'):
            response = reader.obj(c + '/response.json')
            if isinstance(response, dict) and isinstance(response.get('controller'), str):
                raw = response['controller'].encode('utf-8')
                if PRIVATE.search(raw.decode()): raise ValueError('Sensitive pattern in exact candidate; manual review required')
                name = f'generation-{index+1:02d}/controller.py'
                files[name] = raw
                row.update(artifact_available=True, controller_file=name, controller_sha256=sha(raw), controller_bytes=len(raw))
                artifact = f'candidate-{index:02d}/controller.py'
                if not reader.exists(artifact): audits.append('missing_candidate_source_' + str(index + 1))
                elif reader.raw(artifact) != raw: audits.append('generation_source_mismatch_' + str(index + 1))
                check = f'check-{index:02d}/result.json'
                if reader.exists(check):
                    result, fb = sanitize_result(reader.obj(check), 'evaluation' if index == 2 else 'dev', sha(raw), frozen)
                    result['source_result_sha256'] = reader.reads[check]
                    row['aggregate_feedback'] = fb
                    row['audit_problems'] = result['audit_problems']
                    audits.extend('generation_' + str(index + 1) + '_' + problem for problem in result['audit_problems'])
                    if not fb['provenance_verified']:
                        audits.append('unverified_check_provenance_' + str(index + 1))
                    if reader.exists(f'check-{index:02d}/operator.json'):
                        operator = reader.obj(f'check-{index:02d}/operator.json')
                        row['operator'] = {k: number(operator.get(k)) for k in ('return_code', 'queue_seconds', 'seconds')}
                        if operator.get('return_code') != 0: audits.append('abnormal_check_exit_' + str(index + 1))
                    else: audits.append('missing_check_operator_' + str(index + 1))
                    if index == 2:
                        files['final-evaluation.json'] = json_bytes(result)
                else:
                    row['check_status'] = 'result_missing_unscored'
                    audits.append('missing_check_result_' + str(index + 1))
        generations.append(row)
    if summary.get('status') != 'completed': audits.append('incomplete_researcher_run')
    if not all(g['artifact_available'] for g in generations): audits.append('missing_generation_artifact')
    if not all(g.get('inference', {}).get('complete_call_evidence') for g in generations): audits.append('incomplete_call_evidence')
    if not source_ok: audits.append('frozen_pilot_source_mismatch')
    if not packet_ok: audits.append('public_packet_mismatch')
    if not baseline_ok: audits.append('matched_baseline_mismatch')
    complete = (summary.get('status') == 'completed' and source_ok and packet_ok and baseline_ok and not audits
                and all(g.get('inference', {}).get('complete_call_evidence') and g['artifact_available'] for g in generations))
    final = generations[2].get('aggregate_feedback', {})
    score = final.get('primary_score') if complete else None
    if summary.get('final_candidate_sha256') != generations[2].get('controller_sha256'): audits.append('final_artifact_hash_mismatch')
    if score is not None and not close(score, summary.get('final_evaluation', {}).get('primary_score')): audits.append('pilot_final_score_mismatch')
    expected_usage = {k: v for k, v in summary.get('known_usage', {}).items() if k in TOKENS}
    usage_ok = (summary.get('usage_complete') is True and dict(combined_usage) == expected_usage
                and summary.get('calls_attempted') == 3 and summary.get('calls_completed') == 3
                and 'call_directory_inventory_mismatch' not in audits
                and summary.get('total_input_plus_output_tokens') == combined_usage['input_tokens'] + combined_usage['output_tokens'])
    if not usage_ok: audits.append('incomplete_or_inconsistent_usage')
    if audits:
        score = None
        if 'final-evaluation.json' in files:
            demoted = json.loads(files['final-evaluation.json'])
            demoted['reported_primary_score_fraction'] = demoted['primary_score_fraction']
            demoted['primary_score_fraction'] = None
            demoted['status'] = 'unscored'
            demoted['outer_pilot_audit_problems'] = sorted(set(audits))
            files['final-evaluation.json'] = json_bytes(demoted)
    public = {'schema_version': 1, 'scope': 'one three-call tool-free researcher attempt per provider alias; frozen inner MARL policies, no inner LLM calls',
              'model_requested': requested, 'source_git_commit': COMMIT, 'declared_calls': 3,
              'researcher_status': summary.get('status') if summary.get('status') in ('completed', 'unscored_infrastructure_or_invalid_response', 'unscored_source_changed') else 'other',
              'audit_status': 'verified' if not audits else 'needs_review', 'audit_problems': sorted(set(audits)),
              'source_unchanged_and_matches_frozen_commit': source_ok, 'public_packet_matches_declaration': packet_ok,
              'matched_baseline_verified': baseline_ok, 'matched_baseline_result_sha256': study['matched_baseline_result_sha256'],
              'matched_baseline_primary_score_fraction': study['matched_baseline_score'], 'primary_score_fraction': score,
              'coordination_gain_fraction': score - study['matched_baseline_score'] if score is not None else None,
              'usage_complete_and_consistent': usage_ok, 'known_usage': dict(combined_usage),
              'total_input_plus_output_tokens': combined_usage['input_tokens'] + combined_usage['output_tokens'] if usage_ok else None,
              'cached_and_reasoning_tokens_are_subsets': True, 'researcher_host_wall_seconds': number(summary.get('seconds')),
              'generations': generations, 'source_sha256': sources, 'packet_manifest': packet,
              'raw_summary_sha256': reader.reads['summary.json'],
              'limitations': ['One attempt per alias; no model population or variance claim', 'A three-call tool-free pilot is not a full 24-hour OpenRSI trial', 'Reward fractions are not pass rates and natural termination is not success', 'Public canonical evaluation worlds are not secret heldout data', 'No immutable researcher model-server snapshot is exposed', 'Exact generated code is preserved; prompts, reasoning, notes and private logs are excluded']}
    if extra_calls:
        public['unexpected_calls'] = extra_calls
        public['known_extra_usage'] = dict(extra_usage)
        public['known_input_plus_output_tokens_including_extra_calls'] = combined_usage['input_tokens'] + combined_usage['output_tokens']
    files['summary.json'] = json_bytes(public)
    files['README.md'] = b'# Public researcher pilot evidence\n\nExact controller source is retained for every available generation. Only aggregate development feedback is exported. Final results retain every evaluation world, including invalid or infrastructure outcomes. Model reasoning, implementation notes, prompts, private paths, and logs are excluded. Do not execute generated source on the host.\n'
    for raw in files.values():
        if PRIVATE.search(raw.decode('utf-8')): raise ValueError('Private pattern detected in public output')
    reader.verify()
    files['MANIFEST.json'] = json_bytes({k: sha(v) for k, v in sorted(files.items())})
    output.mkdir(parents=True)
    for name, raw in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return public


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.run.resolve(), args.repo.resolve(), args.output.resolve())
    print(json.dumps({k: result[k] for k in ('model_requested', 'audit_status', 'audit_problems', 'primary_score_fraction', 'usage_complete_and_consistent')}, indent=2))

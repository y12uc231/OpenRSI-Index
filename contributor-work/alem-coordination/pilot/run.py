"""Three-call local researcher pilot; execute candidates only via Docker runner.

Private prompts/events remain in the operator-selected output directory. This
script never imports candidate source, and never returns evaluation trajectories
to a model. The existing audited Codex transport supplies model usage records.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('gpt-6-astra', 'gpt-6-sol')
TRANSPORT = ROOT.parent / 'relayrepair/pilot/codex_runner.py'
COMPATIBLE_TRANSPORT = ROOT.parent / 'livemigrate/pilot/compatible_adapter.py'
OPEN_MODEL_PROFILE = ROOT.parent / 'livemigrate/compute/qwen38.json'


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def public_packet(directory):
    manifest = json.loads((directory / 'MANIFEST.json').read_text())
    pieces = []
    for name, expected in sorted(manifest.items()):
        path = directory / name
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe packet path')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Public packet changed: ' + name)
        pieces.append('\nPUBLIC FILE ' + name + '\n' + raw.decode())
    return '\n'.join(pieces), manifest


def feedback(value):
    """Reuse the trusted runner's aggregate-only feedback boundary."""
    spec = importlib.util.spec_from_file_location('alem_public_feedback', ROOT / 'controller/feedback.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.public_feedback(value)


def run_check(args, candidate, suite, output):
    command = [sys.executable, str(ROOT / 'controller/launcher.py'),
               '--source', str(args.source), '--assets', str(args.assets),
               '--environment-image', args.environment_image,
               '--candidate', str(candidate), '--suite', suite, '--output', str(output)]
    begin = time.monotonic()
    try:
        # Concurrent research calls may overlap, but only one simulator is
        # evaluated at a time on this host. Queue time is recorded separately.
        with args.evaluation_lock.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            queue_seconds = time.monotonic() - begin
            process = subprocess.run(command, capture_output=True, text=True, timeout=10860)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'operator-stdout.local.txt').write_text(process.stdout)
        (output / 'operator-stderr.local.txt').write_text(process.stderr)
        path = output / 'result.json'
        if path.is_file():
            value = json.loads(path.read_text())
        else:
            value = {'status': 'infrastructure_or_incomplete',
                     'error': {'type': 'MissingResult'}, 'score': None}
        if process.returncode != 0 or value.get('provenance_verified') is not True:
            # Retain raw result.json as local diagnostic; never accept a score
            # after a failed final provenance check or abnormal launcher exit.
            value = {'status': 'infrastructure_or_incomplete', 'primary_score': None,
                     'total': 20 if suite == 'evaluation' else 4, 'cases': [],
                     'metrics_mean': {}, 'error': {'type': 'LauncherOrProvenanceFailure'}}
        dump(output / 'operator.json', {'return_code': process.returncode,
                                      'queue_seconds': queue_seconds,
                                      'seconds': time.monotonic() - begin})
        return value
    except subprocess.TimeoutExpired:
        output.mkdir(parents=True, exist_ok=True)
        value = {'status': 'infrastructure_or_incomplete', 'score': None,
                 'error': {'type': 'OperatorTimeout'}}
        dump(output / 'operator-timeout.json', value)
        return value


def source_identity():
    files = [ROOT / 'TASK_DESIGN.md', ROOT / 'pilot/PROTOCOL.md', TRANSPORT, COMPATIBLE_TRANSPORT,
             OPEN_MODEL_PROFILE]
    files += sorted((ROOT / 'pilot').glob('*.py'))
    files += sorted((ROOT / 'controller').rglob('*.py'))
    files += sorted((ROOT / 'controller').rglob('*.md'))
    files += [ROOT / 'baseline/common.py', ROOT / 'baseline/source-manifest.json',
              ROOT / 'baseline/asset-manifest.json']
    return {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else '../' + str(path.relative_to(ROOT.parent)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files if '__pycache__' not in path.parts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--adapter-command', nargs='+', help='Prepared JSON stdin/stdout external model transport')
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--environment-image', required=True)
    parser.add_argument('--baseline-result', type=Path, required=True)
    parser.add_argument('--evaluation-lock', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.adapter_command and args.model not in MODELS:
        parser.error('Without --adapter-command use one of: ' + ', '.join(MODELS))
    for name in ('packet', 'source', 'assets', 'output', 'baseline_result', 'evaluation_lock'):
        setattr(args, name, getattr(args, name).resolve())
    packet, packet_manifest = public_packet(args.packet)
    baseline_bytes = args.baseline_result.read_bytes()
    baseline = json.loads(baseline_bytes)
    reference_feedback = feedback(baseline)
    if (baseline.get('provenance_verified') is not True or baseline.get('suite') != 'evaluation'
            or reference_feedback['status'] != 'scored' or reference_feedback['total'] != 20):
        raise ValueError('A verified full matched pass-through result is required before inference')
    baseline_provenance = baseline['host_provenance']
    baseline_hashes = baseline_provenance['hashes']
    reference_path = ROOT / 'controller/reference/controller.py'
    if (baseline_provenance['environment_image'] != args.environment_image
            or baseline_hashes['candidate_sha256'] != hashlib.sha256(reference_path.read_bytes()).hexdigest()):
        raise ValueError('Baseline is not the matched pass-through/environment image')
    for name, expected in baseline_hashes['runner_sha256'].items():
        if hashlib.sha256((ROOT / 'controller' / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Controller runner differs from the baseline: ' + name)
    if not (ROOT / 'controller/launcher.py').is_file():
        raise RuntimeError('Controller validation must finish before inference')
    args.output.mkdir(parents=True, exist_ok=False)
    before = source_identity()
    dump(args.output / 'source-sha256.json', before)
    dump(args.output / 'packet-manifest.json', packet_manifest)
    backend = None
    if not args.adapter_command:
        spec = importlib.util.spec_from_file_location('alem_local_codex_transport', TRANSPORT)
        backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend)
        backend.MODEL, backend.EFFORT = args.model, 'ultra'

    def infer(prompt, directory, output_schema):
        if backend is not None:
            return backend.infer(prompt, directory, output_schema, timeout=1800)
        directory.mkdir(exist_ok=False)
        request = {'prompt': prompt, 'schema': output_schema,
                   'metadata_path': str(directory / 'metadata.json')}
        dump(directory / 'request.local.json', request)
        process = subprocess.run(args.adapter_command, input=json.dumps(request), capture_output=True,
                                 text=True, timeout=1860)
        (directory / 'stdout.local.json').write_text(process.stdout)
        (directory / 'stderr.local.txt').write_text(process.stderr)
        process.check_returncode()
        envelope = json.loads(process.stdout)
        if (not isinstance(envelope, dict) or set(envelope) != {'response', 'metadata'}
                or not isinstance(envelope['metadata'], dict)):
            raise ValueError('Adapter requires response/metadata envelope')
        metadata = envelope['metadata']
        dump(directory / 'metadata.json', metadata)
        if metadata.get('status') != 'completed' or metadata.get('model_requested') != args.model:
            raise ValueError('Incomplete or mismatched external model response')
        dump(directory / 'response.json', envelope['response'])
        return envelope['response']
    code = ('def initialize(agent_id, schema):\n    return {}\n\n'
            'def act(local, memory):\n    return {"action":local["proposal"],"memory":memory}\n')
    observations = [{'matched_reference_aggregate': reference_feedback}]
    schema = {'type': 'object', 'properties': {'controller': {'type': 'string'},
              'note': {'type': 'string'}}, 'required': ['controller', 'note'],
              'additionalProperties': False}
    result = {'status': 'running', 'model_requested': args.model,
              'reasoning_effort': 'ultra' if backend else 'external_profile', 'declared_calls': 3,
              'scope': 'short tool-free researcher feasibility pilot',
              'transport_sha256': hashlib.sha256(TRANSPORT.read_bytes()).hexdigest(),
              'calls_attempted': 0,
              'matched_baseline_sha256': hashlib.sha256(baseline_bytes).hexdigest(),
              'matched_baseline_primary_score': reference_feedback['primary_score']}
    result['source_git_commit'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    start = time.monotonic()
    try:
        for index in range(3):
            prompt = (
                'Develop a reusable decentralized controller that improves frozen-team '
                'coordination reward in Alem. Return complete Python standard-library '
                'controller.py source and a brief implementation note. You have no direct '
                'tools; the controller tests all four development worlds after calls one '
                'and two and returns aggregate feedback. The third artifact is final. '
                'Do not alter the environment, inspect evaluator internals, use external '
                'services or hard-code worlds. You may retain the pass-through if your '
                'hypothesis does not warrant changing it. Any legal action is allowed. '
                'The three game actors are separate instances of your source; they '
                'communicate only through native game actions. This is call '
                f'{index + 1}/3.\n' + packet + '\nCURRENT CONTROLLER:\n' + code +
                '\nYOUR DEVELOPMENT FEEDBACK:\n' + json.dumps(observations))
            result['calls_attempted'] += 1
            response = infer(prompt, args.output / f'call-{index:02d}', schema)
            if set(response) != {'controller', 'note'} or any(not isinstance(v, str) for v in response.values()):
                raise ValueError('Malformed response; no replacement generation')
            code = response['controller']
            candidate = args.output / f'candidate-{index:02d}'
            candidate.mkdir()
            (candidate / 'controller.py').write_text(code)
            artifact_hash = hashlib.sha256((candidate / 'controller.py').read_bytes()).hexdigest()
            suite = 'evaluation' if index == 2 else 'dev'
            value = run_check(args, candidate, suite, args.output / f'check-{index:02d}')
            if hashlib.sha256((candidate / 'controller.py').read_bytes()).hexdigest() != artifact_hash:
                raise RuntimeError('Candidate changed during execution')
            observations.append({'call': index + 1, 'suite': suite, **feedback(value)})
            if index == 2:
                result['final_candidate_sha256'] = artifact_hash
                result['final_evaluation'] = feedback(value)
                if result['final_evaluation']['primary_score'] is not None:
                    result['coordination_gain_fraction'] = (result['final_evaluation']['primary_score']
                                                            - result['matched_baseline_primary_score'])
        result['status'] = 'completed'
    except Exception as exc:
        result['status'] = 'unscored_infrastructure_or_invalid_response'
        result['error_type'] = type(exc).__name__
        raise
    finally:
        result['seconds'] = time.monotonic() - start
        result['source_unchanged'] = source_identity() == before
        if not result['source_unchanged']:
            result['status'] = 'unscored_source_changed'
        result['observations'] = observations
        usage = {}
        completed = 0
        usage_complete = True
        for path in sorted(args.output.glob('call-*/metadata.json')):
            value = json.loads(path.read_text())
            completed += value.get('status') == 'completed'
            records = value.get('usage', [])
            if (value.get('status') != 'completed' or len(records) != 1 or
                    any(type(records[0].get(k)) is not int for k in ('input_tokens', 'output_tokens'))):
                usage_complete = False
            for item in value.get('usage', []):
                for key, count in item.items():
                    if type(count) is int:
                        usage[key] = usage.get(key, 0) + count
        result['calls_completed'] = completed
        result['usage_complete'] = usage_complete and completed == result['calls_attempted']
        result['known_usage'] = usage
        result['total_input_plus_output_tokens'] = (usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
                                                   if result['usage_complete'] else None)
        result['cached_and_reasoning_tokens_are_subsets'] = True
        dump(args.output / 'summary.json', result)


if __name__ == '__main__':
    main()

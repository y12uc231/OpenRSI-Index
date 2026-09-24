"""A small, transparent coding-team feasibility pilot.

Models receive only an explicit public packet and return source strings. They
cannot inspect this checkout, reference solutions, evaluation schedules, or
another call's private reasoning. Generated Python is never imported here.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

CORE_ROOT = Path(__file__).resolve().parents[1]
ROLES = ('db', 'api', 'consumer')
IMAGE = 'python@sha256:23b5dc88c7dd47fec3f960b51dc30d19df9875cfbfc60f3b62d3e5b88cbccf62'
LOCAL_MODELS = ('gpt-6-astra', 'gpt-6-sol')


class LocalInferenceInfrastructureError(RuntimeError):
    infrastructure_error = True


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def schema(roles):
    keys = list(roles) + ['message']
    return {'type': 'object', 'properties': {k: {'type': 'string'} for k in keys},
            'required': keys, 'additionalProperties': False}


def source_hashes(task_root=CORE_ROOT):
    hashes = {str(p.relative_to(CORE_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(CORE_ROOT.rglob('*')) if p.is_file()
              and '__pycache__' not in p.parts and p.suffix in ('.py', '.md', '.json')}
    task_root = Path(task_root).resolve()
    if task_root != CORE_ROOT:
        hashes.update({'task/' + str(p.relative_to(task_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(task_root.rglob('*')) if p.is_file()
                       and '__pycache__' not in p.parts and p.suffix in ('.py', '.md', '.json')})
    adapter = CORE_ROOT.parent / 'relayrepair' / 'pilot' / 'codex_runner.py'
    hashes['../relayrepair/pilot/codex_runner.py'] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    return hashes


def check(candidate, suite, destination, task_root=CORE_ROOT):
    # Keep expected operation history outside the candidate process and mounts.
    if not (CORE_ROOT / 'isolated.py').exists():
        raise RuntimeError('Isolated evaluator must be implemented before model inference')
    cmd = [sys.executable, str(CORE_ROOT / 'isolated.py'), '--candidate', str(candidate),
           '--suite', suite, '--image', IMAGE, '--task-root', str(Path(task_root).resolve())]
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        destination.write_text(proc.stdout)
        destination.with_suffix('.stderr.txt').write_text(proc.stderr)
        if proc.returncode:
            return {'status': 'check_error', 'exit_code': proc.returncode,
                    'stderr': proc.stderr[-4000:], 'seconds': time.monotonic() - start}
        return json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {'status': 'infrastructure_or_incomplete', 'error': type(exc).__name__}


def load_backend():
    # Reuse the already audited tool-free CLI transport, not the earlier task.
    path = CORE_ROOT.parent / 'relayrepair' / 'pilot' / 'codex_runner.py'
    spec = importlib.util.spec_from_file_location('livemigrate_codex_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def usage_summary(directory):
    totals = {}
    recorded = 0
    incomplete = 0
    for path in sorted(directory.glob('call-*/metadata.json')):
        metadata = json.loads(path.read_text())
        incomplete += metadata.get('usage_complete') is False
        for usage in metadata.get('usage', []):
            recorded += 1
            for key, value in usage.items():
                if type(value) is int:
                    totals[key] = totals.get(key, 0) + value
    return {'calls_with_usage': recorded, 'calls_marked_incomplete_usage': incomplete, 'reported_totals': totals,
            'total_input_plus_output': (totals['input_tokens'] + totals['output_tokens'])
                if 'input_tokens' in totals and 'output_tokens' in totals else None,
            'cached_input_is_subset_not_added_again': True}


def public_packet(task_root=CORE_ROOT):
    """Build an explicit allowlist; solutions and schedules never enter prompts."""
    task_root = Path(task_root).resolve()
    required = ['API_CONTRACT.md', 'runtime.py', 'scenarios.py', 'reference/immutable_v1.py']
    required += ['starter/' + role + '.py' for role in ROLES]
    for name in required:
        if not (task_root / name).is_file():
            raise RuntimeError('Task root requires ' + name)
    packet = (task_root / 'API_CONTRACT.md').read_text()
    name = 'reference/immutable_v1.py'
    packet += '\nIMMUTABLE PUBLIC SOURCE ' + name + '\n' + (task_root / name).read_text()
    code = {role: (task_root / 'starter' / (role + '.py')).read_text() for role in ROLES}
    return packet, code


def record_adapter_response(value, call_dir):
    """Accept legacy schema output or one strict response/metadata envelope."""
    if not isinstance(value, dict):
        raise ValueError('Adapter stdout must be a JSON object')
    if 'response' in value or 'metadata' in value:
        if set(value) != {'response', 'metadata'} or not isinstance(value['response'], dict) or not isinstance(value['metadata'], dict):
            raise ValueError('Adapter envelope requires exactly response and metadata objects')
        response = value['response']
        # Metadata comes only from the operator-selected adapter executable.
        # A model's source/message fields are never interpreted as usage data.
        dump(call_dir / 'metadata.json', value['metadata'])
    else:
        response = value
    dump(call_dir / 'response.json', response)
    return response


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('team', 'centralized'), required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--adapter-command', nargs='+', help='Optional JSON stdin/stdout model adapter; see PROTOCOL.md.')
    ap.add_argument('--local-model', choices=LOCAL_MODELS,
                    help='Local CLI model alias; defaults to gpt-6-astra, both use ultra reasoning')
    ap.add_argument('--task-root', type=Path, default=CORE_ROOT,
                    help='Trusted task folder; defaults to the original migration family')
    ap.add_argument('--inference-timeout', type=int, default=480,
                    help='Per-call transport deadline in seconds for either backend (default: 480)')
    ap.add_argument('--scaffold', type=Path,
                    help='Optional declarative instructions/wave schedule; requires team mode')
    args = ap.parse_args(argv)
    if args.inference_timeout <= 0:
        ap.error('--inference-timeout must be positive')
    if args.local_model is not None and args.adapter_command:
        ap.error('--local-model cannot be combined with --adapter-command')
    policy = None
    if args.scaffold:
        if args.mode != 'team':
            ap.error('--scaffold requires --mode team')
        spec = importlib.util.spec_from_file_location('livemigrate_policy', CORE_ROOT / 'pilot' / 'scaffold.py')
        policy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy_module)
        policy = policy_module.load(args.scaffold)
    task_root = args.task_root.resolve()
    out = args.output.resolve()
    if not (CORE_ROOT / 'isolated.py').exists():
        raise RuntimeError('Missing isolated evaluator; refusing to start pilot')
    packet, code = public_packet(task_root)
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    hashes = source_hashes(task_root)
    dump(out / 'source-sha256.json', hashes)
    if policy is not None:
        dump(out / 'scaffold.json', policy)
    backend = None if args.adapter_command else load_backend()
    model_selection_source = ('local_model_argument' if args.local_model is not None else
                              'local_cli_default' if backend else 'external_adapter')
    if backend:
        # load_backend returns a fresh module; only this run's request globals
        # change. The shared transport file and prior run artifacts stay intact.
        backend.MODEL = args.local_model or LOCAL_MODELS[0]
        backend.EFFORT = 'ultra'
    observations, messages = [], []
    call_index = 0

    def infer(prompt, call_dir, output_schema):
        if backend:
            metadata = None
            try:
                return backend.infer(prompt, call_dir, output_schema, timeout=args.inference_timeout)
            except Exception as exc:
                path = call_dir / 'metadata.json'
                if path.is_file():
                    try:
                        metadata = json.loads(path.read_text())
                        if not isinstance(metadata, dict):
                            metadata = None
                    except (ValueError, UnicodeError):
                        pass
                if (metadata is None or metadata.get('status') == 'timeout' or
                        (type(metadata.get('return_code')) is int and metadata['return_code'] != 0)):
                    raise LocalInferenceInfrastructureError('Local CLI inference did not complete; see local call metadata') from exc
                raise
            finally:
                path = call_dir / 'metadata.json'
                if path.is_file():
                    try:
                        metadata = json.loads(path.read_text())
                    except (ValueError, UnicodeError):
                        metadata = None
                    if isinstance(metadata, dict):
                        metadata.setdefault('model_requested', backend.MODEL)
                        metadata.setdefault('reasoning_effort', backend.EFFORT)
                        metadata['model_selection_source'] = model_selection_source
                        dump(path, metadata)
        call_dir.mkdir()
        request = {'prompt': prompt, 'schema': output_schema,
                   'metadata_path': str(call_dir / 'metadata.json')}
        dump(call_dir / 'request.json', request)
        process = subprocess.run(args.adapter_command, input=json.dumps(request), capture_output=True,
            text=True, timeout=args.inference_timeout)
        (call_dir / 'stdout.json').write_text(process.stdout)
        (call_dir / 'stderr.local.txt').write_text(process.stderr)
        process.check_returncode()
        return record_adapter_response(json.loads(process.stdout), call_dir)

    def task(owned, snapshot, index, stage):
        extra = ''
        if policy is not None:
            if policy['shared_instruction']:
                extra += '\nCOORDINATION INSTRUCTION:\n' + policy['shared_instruction']
            if policy['role_instructions'][owned[0]]:
                extra += '\nROLE INSTRUCTION:\n' + policy['role_instructions'][owned[0]]
        prompt = (
            'Implement the specified live software migration. You are writing actual Python3 source. '
            'You have no direct tools; a controller executes public checks after each group of three calls. '
            'Use the full specification. All agents share the same objective and the entire public packet. '
            'Do not seek evaluator internals, inspect caller frames, alter the runtime or fabricate results. '
            'Return complete replacement source for your owned files and a concrete message for your teammates.\n'
            f'Own exactly: {list(owned)}. Mode: {args.mode}. Call: {index + 1}/6. Stage: {stage}.\n'
            'PUBLIC SPECIFICATION:\n' + packet + '\nCURRENT ALL-ROLE SOURCE:\n' + json.dumps(snapshot) +
            '\nTEAM MESSAGES:\n' + json.dumps(messages) + '\nPUBLIC CHECK OBSERVATIONS:\n' + json.dumps(observations) + extra
        )
        response = infer(prompt, out / f'call-{index:02d}', schema(owned))
        if set(response) != set(owned) | {'message'} or any(not isinstance(v, str) for v in response.values()):
            raise ValueError('Malformed model output; no hidden replacement generation')
        return response

    try:
        for stage in range(2):
            if args.mode == 'team':
                waves = policy['stages'][stage] if policy is not None else [ROLES]
                for wave in waves:
                    snapshot = dict(code)
                    with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                        futures = [pool.submit(task, (role,), snapshot, call_index + i, stage)
                                   for i, role in enumerate(wave)]
                        responses = [future.result() for future in futures]
                    for role, response in zip(wave, responses):
                        code[role] = response[role]
                        messages.append({'stage': stage, 'role': role, 'message': response['message']})
                    call_index += len(wave)
            else:
                for _ in range(3):
                    response = task(ROLES, dict(code), call_index, stage)
                    code = {role: response[role] for role in ROLES}
                    messages.append({'stage': stage, 'role': 'centralized', 'message': response['message']})
                    call_index += 1
            candidate = out / f'candidate-{stage}'
            candidate.mkdir()
            for role, source in code.items():
                (candidate / (role + '.py')).write_text(source)
            observation = check(candidate, 'public', out / f'public-{stage}.json', task_root)
            observations.append(observation)
        frozen_candidate = {role: hashlib.sha256(source.encode()).hexdigest() for role, source in code.items()}
        dump(out / 'candidate-sha256.json', frozen_candidate)
        final = check(candidate, 'heldout', out / 'heldout.json', task_root)
        result = {'status': final.get('status', 'unknown_check_status'),
                  'generation_completed': True, 'mode': args.mode, 'calls': call_index,
                  'task_root': str(task_root), 'core_root': str(CORE_ROOT),
                  'inference_timeout_seconds': args.inference_timeout,
                  'infrastructure_affected': any(observation.get('status') in
                      ('check_error', 'infrastructure_or_incomplete') for observation in observations),
                  'requested_model': backend.MODEL if backend else 'external_adapter',
                  'reasoning_effort': backend.EFFORT if backend else 'adapter_declared',
                  'model_selection_source': model_selection_source,
                  'candidate_sha256': frozen_candidate, 'public': observations, 'heldout': final,
                  'usage': usage_summary(out),
                  'seconds': round(time.monotonic() - start, 3),
                  'scope': 'one task family; schedules are correlated stress cases, not independent tasks'}
        if policy is not None:
            result['scaffold_sha256'] = hashlib.sha256((out / 'scaffold.json').read_bytes()).hexdigest()
        dump(out / 'summary.json', result)
        print(json.dumps(result), flush=True)
    except Exception as exc:
        dump(out / 'failure.json', {'status': 'incomplete', 'error': type(exc).__name__,
                                   'message': str(exc), 'seconds': time.monotonic() - start,
                                   'failure_category': 'infrastructure' if getattr(exc, 'infrastructure_error', False) else 'incomplete_or_invalid_generation',
                                   'infrastructure_affected': bool(getattr(exc, 'infrastructure_error', False)),
                                   'requested_model': backend.MODEL if backend else 'external_adapter',
                                   'reasoning_effort': backend.EFFORT if backend else 'adapter_declared',
                                   'model_selection_source': model_selection_source,
                                   'usage': usage_summary(out)})
        raise


if __name__ == '__main__':
    main()

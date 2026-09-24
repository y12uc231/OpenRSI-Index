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

ROOT = Path(__file__).resolve().parents[1]
ROLES = ('db', 'api', 'consumer')
IMAGE = 'python@sha256:23b5dc88c7dd47fec3f960b51dc30d19df9875cfbfc60f3b62d3e5b88cbccf62'


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def schema(roles):
    keys = list(roles) + ['message']
    return {'type': 'object', 'properties': {k: {'type': 'string'} for k in keys},
            'required': keys, 'additionalProperties': False}


def source_hashes():
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(ROOT.rglob('*')) if p.is_file()
              and '__pycache__' not in p.parts and p.suffix in ('.py', '.md', '.json')}
    adapter = ROOT.parent / 'relayrepair' / 'pilot' / 'codex_runner.py'
    hashes['../relayrepair/pilot/codex_runner.py'] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    return hashes


def check(candidate, suite, destination):
    # Keep expected operation history outside the candidate process and mounts.
    if not (ROOT / 'isolated.py').exists():
        raise RuntimeError('Isolated evaluator must be implemented before model inference')
    cmd = [sys.executable, str(ROOT / 'isolated.py'), '--candidate', str(candidate),
           '--suite', suite, '--image', IMAGE]
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
    path = ROOT.parent / 'relayrepair' / 'pilot' / 'codex_runner.py'
    spec = importlib.util.spec_from_file_location('livemigrate_codex_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def usage_summary(directory):
    totals = {}
    recorded = 0
    for path in sorted(directory.glob('call-*/metadata.json')):
        metadata = json.loads(path.read_text())
        for usage in metadata.get('usage', []):
            recorded += 1
            for key, value in usage.items():
                if type(value) is int:
                    totals[key] = totals.get(key, 0) + value
    return {'calls_with_usage': recorded, 'reported_totals': totals,
            'total_input_plus_output': (totals['input_tokens'] + totals['output_tokens'])
                if 'input_tokens' in totals and 'output_tokens' in totals else None,
            'cached_input_is_subset_not_added_again': True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('team', 'centralized'), required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--adapter-command', nargs='+', help='Optional JSON stdin/stdout model adapter; see PROTOCOL.md.')
    args = ap.parse_args()
    out = args.output.resolve()
    if not (ROOT / 'isolated.py').exists():
        raise RuntimeError('Missing isolated evaluator; refusing to start pilot')
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    hashes = source_hashes()
    dump(out / 'source-sha256.json', hashes)
    packet = (ROOT / 'API_CONTRACT.md').read_text()
    name = 'reference/immutable_v1.py'
    packet += '\nIMMUTABLE PUBLIC SOURCE ' + name + '\n' + (ROOT / name).read_text()
    code = {r: (ROOT / 'starter' / (r + '.py')).read_text() for r in ROLES}
    backend = None if args.adapter_command else load_backend()
    observations, messages = [], []
    call_index = 0

    def infer(prompt, call_dir, output_schema):
        if backend:
            return backend.infer(prompt, call_dir, output_schema)
        call_dir.mkdir()
        dump(call_dir / 'request.json', {'prompt': prompt, 'schema': output_schema})
        process = subprocess.run(args.adapter_command, input=json.dumps(
            {'prompt': prompt, 'schema': output_schema}), capture_output=True,
            text=True, timeout=480)
        (call_dir / 'stdout.json').write_text(process.stdout)
        (call_dir / 'stderr.local.txt').write_text(process.stderr)
        process.check_returncode()
        response = json.loads(process.stdout)
        dump(call_dir / 'response.json', response)
        return response

    def task(owned, snapshot, index, stage):
        prompt = (
            'Implement the specified live software migration. You are writing actual Python3 source. '
            'You have no direct tools; a controller executes public checks after each group of three calls. '
            'Use the full specification. All agents share the same objective and the entire public packet. '
            'Do not seek evaluator internals, inspect caller frames, alter the runtime or fabricate results. '
            'Return complete replacement source for your owned files and a concrete message for your teammates.\n'
            f'Own exactly: {list(owned)}. Mode: {args.mode}. Call: {index + 1}/6. Stage: {stage}.\n'
            'PUBLIC SPECIFICATION:\n' + packet + '\nCURRENT ALL-ROLE SOURCE:\n' + json.dumps(snapshot) +
            '\nTEAM MESSAGES:\n' + json.dumps(messages) + '\nPUBLIC CHECK OBSERVATIONS:\n' + json.dumps(observations)
        )
        response = infer(prompt, out / f'call-{index:02d}', schema(owned))
        if set(response) != set(owned) | {'message'} or any(not isinstance(v, str) for v in response.values()):
            raise ValueError('Malformed model output; no hidden replacement generation')
        return response

    try:
        for stage in range(2):
            if args.mode == 'team':
                snapshot = dict(code)
                with ThreadPoolExecutor(max_workers=3) as pool:
                    futures = [pool.submit(task, (role,), snapshot, call_index + i, stage)
                               for i, role in enumerate(ROLES)]
                    responses = [future.result() for future in futures]
                for role, response in zip(ROLES, responses):
                    code[role] = response[role]
                    messages.append({'stage': stage, 'role': role, 'message': response['message']})
                call_index += 3
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
            observation = check(candidate, 'public', out / f'public-{stage}.json')
            observations.append(observation)
        frozen_candidate = {role: hashlib.sha256(source.encode()).hexdigest() for role, source in code.items()}
        dump(out / 'candidate-sha256.json', frozen_candidate)
        final = check(candidate, 'heldout', out / 'heldout.json')
        result = {'status': final.get('status', 'unknown_check_status'),
                  'generation_completed': True, 'mode': args.mode, 'calls': call_index,
                  'requested_model': backend.MODEL if backend else 'external_adapter',
                  'reasoning_effort': backend.EFFORT if backend else 'adapter_declared',
                  'candidate_sha256': frozen_candidate, 'public': observations, 'heldout': final,
                  'usage': usage_summary(out),
                  'seconds': round(time.monotonic() - start, 3),
                  'scope': 'one task family; schedules are correlated stress cases, not independent tasks'}
        dump(out / 'summary.json', result)
        print(json.dumps(result), flush=True)
    except Exception as exc:
        dump(out / 'failure.json', {'status': 'incomplete', 'error': type(exc).__name__,
                                   'message': str(exc), 'seconds': time.monotonic() - start})
        raise


if __name__ == '__main__':
    main()

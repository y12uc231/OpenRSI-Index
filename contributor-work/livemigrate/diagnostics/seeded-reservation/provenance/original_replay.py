"""Replay a sealed exploratory pack through Docker; never import candidate code."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--index', type=int, choices=range(20), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pack, candidate, output = args.pack.resolve(), args.candidate.resolve(), args.output.resolve()
    if output.exists():
        parser.error('output already exists; no overwrite or replacement replay')
    seal_bytes = (pack / 'SEALED.json').read_bytes()
    seal = json.loads(seal_bytes)
    expected = seal['source_sha256']
    candidate_hashes = {role: digest(candidate / (role + '.py')) for role in ('db', 'api', 'consumer')}

    def verify():
        if (pack / 'SEALED.json').read_bytes() != seal_bytes:
            raise ValueError('seal changed')
        for name, value in expected.items():
            path = (pack / name).resolve()
            if not path.is_relative_to(pack) or digest(path) != value:
                raise ValueError('sealed source changed: ' + name)
        if candidate_hashes != {role: digest(candidate / (role + '.py')) for role in candidate_hashes}:
            raise ValueError('candidate changed')

    verify()
    sys.path.insert(0, str(pack / 'task'))
    sys.path.insert(0, str(pack / 'transport'))
    import runtime
    import scenarios
    import isolated

    start = time.monotonic()
    try:
        with isolated.MultiStoreInvoker(candidate, legacy_helper=pack / 'task/reference/immutable_v1.py') as invoke:
            result = runtime.execute(candidate, scenarios.make_case(args.index), invoke=invoke)
    except Exception as exc:
        result = {'status': 'infrastructure_or_incomplete', 'passed': False, 'score': None,
                  'error_type': type(exc).__name__}
    verify()
    record = {'scope': 'exploratory seeded schedule coverage; original model scores unchanged',
              'index': args.index, 'split': 'calibration' if args.index < 4 else 'evaluation',
              'seal_sha256': hashlib.sha256(seal_bytes).hexdigest(),
              'runner_sha256': digest(Path(__file__)), 'candidate_sha256': candidate_hashes,
              'source_verified': True, 'model_calls': 0, 'seconds': time.monotonic() - start,
              'result': result}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as handle:
        handle.write(json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'index': args.index, 'status': result['status'], 'passed': result['passed'],
                      'seconds': round(record['seconds'], 3)}), flush=True)


if __name__ == '__main__':
    main()

"""Exploratory concurrency coverage; isolated replay, never new model inference."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--core-root', type=Path, default=CORE)
    args = parser.parse_args()
    core = args.core_root.resolve()
    candidate = args.candidate.resolve()
    manifest = json.loads((HERE / 'source-manifest.json').read_text())
    expected = manifest['source_sha256']

    def verify():
        if any(digest(core / name) != value for name, value in expected.items()):
            raise ValueError('protected runtime differs from the diagnostic source manifest')

    verify()
    candidate_hashes = {role: digest(candidate / (role + '.py')) for role in ('db', 'api', 'consumer')}
    cases_bytes = (HERE / 'cases.json').read_bytes()
    cases = json.loads(cases_bytes)
    if len(cases) != 3:
        raise ValueError('the exploratory set contains exactly three fixed schedules')
    spec = importlib.util.spec_from_file_location('trusted_concurrency_isolation', core / 'isolated.py')
    isolation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(isolation)
    task = core / 'families/reservation'
    start, outcomes = time.monotonic(), []
    with isolation.task_runtime(task) as runtime:
        for case in cases:
            verify()
            try:
                with isolation.MultiStoreInvoker(candidate, legacy_helper=task / 'reference/immutable_v1.py') as invoke:
                    outcomes.append(runtime.execute(candidate, case, invoke=invoke))
            except Exception as exc:
                outcomes.append({'name': case['name'], 'status': 'infrastructure_or_incomplete',
                                 'passed': False, 'score': None, 'error_type': type(exc).__name__})
    verify()
    if candidate_hashes != {role: digest(candidate / (role + '.py')) for role in candidate_hashes}:
        raise ValueError('candidate source changed during the diagnostic')
    if (HERE / 'cases.json').read_bytes() != cases_bytes:
        raise ValueError('diagnostic cases changed during execution')
    scored = all(case['status'] == 'scored' for case in outcomes)
    passed = sum(case['passed'] for case in outcomes)
    print(json.dumps({'scope': 'separate exploratory coverage; not the preregistered pilot score',
                      'task_source_revision': manifest['task_source_revision'],
                      'cases_sha256': hashlib.sha256(cases_bytes).hexdigest(),
                      'candidate_sha256': candidate_hashes, 'source_verified': True,
                      'model_calls': 0, 'suite': 'exploratory_concurrency',
                      'status': 'scored' if scored else 'unscored',
                      'passed': passed, 'total': 3, 'score': passed / 3 if scored else None,
                      'seconds': time.monotonic() - start, 'cases': outcomes}, allow_nan=False))


if __name__ == '__main__':
    main()

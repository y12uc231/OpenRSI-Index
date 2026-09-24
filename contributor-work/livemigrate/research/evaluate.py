"""Direct evaluation of a declarative coordination artifact on frozen workers.

The GPU lane is prepared, not hardware-validated. This controller is trusted
task code, not part of the candidate action space. Model identity, budgets,
feedback timing and task selection cannot be changed by scaffold.json.
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
FAMILIES = (('amounts', ROOT), ('identity', ROOT / 'families/identity'))


def aggregate(reports):
    """No silent filtering of invalid families or failed feedback delivery."""
    expected = [name for name, _ in FAMILIES]
    if set(reports) != set(expected):
        return {'status': 'incomplete', 'score': None, 'reason': 'missing_family'}
    diagnostics = {}
    for name in expected:
        report = reports[name]
        heldout = report.get('heldout', {})
        cases = heldout.get('cases', [])
        usage = report.get('usage', {})
        total_tokens = usage.get('total_input_plus_output')
        diagnostics[name] = {'status': report.get('status', 'unknown'),
                             'generation_completed': report.get('generation_completed', False),
                             'infrastructure_affected': report.get('infrastructure_affected', False),
                             'passed': heldout.get('passed'), 'total': heldout.get('total'),
                             'usage': report.get('usage')}
        if report.get('status') != 'scored' or report.get('generation_completed') is not True \
                or report.get('infrastructure_affected') is not False \
                or report.get('calls') != 6 or heldout.get('status') != 'scored' \
                or usage.get('calls_with_usage') != 6 or usage.get('calls_marked_incomplete_usage') != 0 \
                or type(total_tokens) is not int or not 0 < total_tokens <= 6 * 32768 \
                or heldout.get('total') != 3 or len(cases) != 3 \
                or len({case.get('name') for case in cases}) != 3 \
                or any(case.get('status') != 'scored' or type(case.get('passed')) is not bool for case in cases):
            return {'status': 'unscored', 'score': None, 'reason': 'invalid_or_incomplete_family',
                    'families': diagnostics}
    # Equal family weight. The three stress traces in each family are correlated.
    per_family = {name: sum(case['passed'] for case in reports[name]['heldout']['cases']) / 3
                  for name in expected}
    return {'status': 'scored', 'score': sum(per_family.values()) / len(per_family),
            'metric': 'macro_family_history_safe_trace_fraction',
            'family_scores': per_family, 'families': diagnostics,
            'scope': 'two public semantic families; no claim of unseen-family transfer'}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--scaffold', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(argv)
    spec = importlib.util.spec_from_file_location('research_policy_validation', ROOT / 'pilot/scaffold.py')
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    policy = validator.load(args.scaffold)
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        ap.error('Use a fresh output directory outside the source tree')
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / 'scaffold.json'
    frozen.write_text(json.dumps(policy, indent=2) + '\n')
    profile = ROOT / 'compute/qwen38.json'
    provenance = {'scaffold_sha256': hashlib.sha256(frozen.read_bytes()).hexdigest(),
                  'model_profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest(),
                  'model_profile': json.loads(profile.read_text()),
                  'calls_per_family': 6, 'families': [name for name, _ in FAMILIES],
                  'max_inclusive_input_output_tokens': 2 * 6 * 32768}
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    reports = {}
    for name, task_root in FAMILIES:
        destination = output / name
        command = [sys.executable, str(ROOT / 'pilot/run.py'), '--mode', 'team',
                   '--scaffold', str(frozen), '--task-root', str(task_root),
                   '--output', str(destination), '--inference-timeout', '1800',
                   '--adapter-command', sys.executable, str(ROOT / 'pilot/compatible_adapter.py'), str(profile)]
        # No retries or replacement runs. The pilot owns per-call deadlines.
        with (output / (name + '.stdout.local.txt')).open('w') as stdout, \
             (output / (name + '.stderr.local.txt')).open('w') as stderr:
            process = subprocess.run(command, stdout=stdout, stderr=stderr)
        summary = destination / 'summary.json'
        failure = destination / 'failure.json'
        if summary.exists():
            reports[name] = json.loads(summary.read_text())
        elif failure.exists():
            reports[name] = json.loads(failure.read_text())
        else:
            reports[name] = {'status': 'incomplete', 'exit_code': process.returncode}
    result = aggregate(reports)
    result['scaffold_sha256'] = provenance['scaffold_sha256']
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()

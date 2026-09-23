"""Explicitly invoke the fixed nine-call pilot through a command transport."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from command_runner import CommandRunner
import run_pilot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--execute', action='store_true', help='Explicitly launch the configured command (may incur provider charges).')
    args = parser.parse_args()
    if not args.execute:
        parser.error('Preparation only: add --execute only when you intend to launch the configured command.')
    runner = CommandRunner(args.config)
    pilot = Path(__file__).resolve().parent
    repo = pilot.parents[2]
    output = args.output.resolve()
    if output == repo or repo in output.parents:
        parser.error('Raw inference output must be outside the Git checkout.')
    output.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__), pilot / 'command_runner.py', pilot / 'run_pilot.py',
             pilot / 'codex_runner.py', pilot / 'PROTOCOL.md', pilot / 'MATRIX.md',
             pilot / 'compatible_chat_command.py', pilot / 'mock_command.py']
    snapshot = {'created_utc': datetime.now(timezone.utc).isoformat(),
                'execution_kind': runner.kind, 'model_requested': runner.model,
                'params': runner.params, 'timeout_seconds': runner.timeout,
                'planned_calls': 9, 'planned_cases_per_call': 12,
                'config_sha256': hashlib.sha256(runner.config_bytes).hexdigest(),
                'code_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    if runner.kind == 'mock':
        snapshot['warning'] = 'DETERMINISTIC TRANSPORT STUB — NOT A MODEL RUN OR PERFORMANCE MEASUREMENT'
    (output / 'run_config.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    (output / 'config.local.json').write_bytes(runner.config_bytes)
    run_pilot.infer = runner.infer
    original_argv = sys.argv
    sys.argv = [str(pilot / 'run_pilot.py'), '--output', str(output / 'calls')]
    status = {'execution_kind': runner.kind, 'status': 'running',
              'is_model_measurement': runner.kind == 'external_model'}
    try:
        with (output / 'runner.local.log').open('w') as log, redirect_stdout(log):
            run_pilot.main()
        result_path = output / 'calls' / 'results.json'
        result = json.loads(result_path.read_text())
        result['execution_kind'] = runner.kind
        result['model_requested'] = runner.model
        result['is_model_measurement'] = runner.kind == 'external_model'
        if runner.kind == 'mock':
            result['measurement_type'] = 'MOCK_TRANSPORT_WIRING_CHECK_NOT_MODEL_EVALUATION'
            result_path.unlink()
            result_path = output / 'calls' / 'mock_fixture_grading.NOT_MODEL.json'
        result_path.write_text(json.dumps(result, indent=2) + '\n')
        status['status'] = 'completed'
    except Exception as error:
        status.update(status='failed', error_kind=type(error).__name__)
        raise
    finally:
        sys.argv = original_argv
        (output / 'run_status.json').write_text(json.dumps(status, indent=2) + '\n')
    print('MOCK wiring check completed; NOT a model result.' if runner.kind == 'mock'
          else 'Configured model pilot completed. Review per-call metadata and results.')


if __name__ == '__main__':
    main()

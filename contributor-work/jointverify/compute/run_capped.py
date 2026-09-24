#!/usr/bin/env python3
"""Run one GPU process under a persistent cumulative eight-hour validation cap.

Linux GPU host only. An interrupted/incomplete ledger fails closed; reconcile
the actual allocation before any further run. Do not delete/reset this ledger.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

CAP_SECONDS = 8 * 60 * 60
SHUTDOWN_RESERVE = 60


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('A command is required after --.')
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    with args.ledger.open('a+') as record:
        fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record.seek(0)
        content = record.read()
        state = json.loads(content) if content else {'cap_gpu_seconds': CAP_SECONDS, 'spent_gpu_seconds': 0.0, 'runs': []}
        if state.get('active'):
            raise SystemExit('Previous allocation has no completed accounting. Reconcile it; do not reset the ledger.')
        if state['cap_gpu_seconds'] != CAP_SECONDS or state['spent_gpu_seconds'] < 0:
            raise SystemExit('Invalid validation budget ledger.')
        remaining = CAP_SECONDS - state['spent_gpu_seconds']
        if remaining <= SHUTDOWN_RESERVE:
            raise SystemExit('Eight GPU-hour validation allowance exhausted.')

        def save():
            record.seek(0)
            record.truncate()
            record.write(json.dumps(state, indent=2) + '\n')
            record.flush()
            os.fsync(record.fileno())

        state['active'] = {'started_at_unix': time.time(), 'reserved_gpu_seconds': remaining}
        save()
        start = time.monotonic()
        process = None
        reason = 'completed'
        code = 1

        def interrupted(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, interrupted)
        try:
            process = subprocess.Popen(command, start_new_session=True)
            code = process.wait(timeout=remaining - SHUTDOWN_RESERVE)
        except subprocess.TimeoutExpired:
            reason, code = 'validation_budget_reached', 124
        except KeyboardInterrupt:
            reason, code = 'interrupted', 130
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
            elapsed = time.monotonic() - start
            state['spent_gpu_seconds'] += elapsed
            state['runs'].append({'started_at_unix': state['active']['started_at_unix'],
                                  'gpu_seconds': elapsed, 'exit_code': code, 'reason': reason})
            state.pop('active')
            save()
        raise SystemExit(code)


if __name__ == '__main__':
    main()

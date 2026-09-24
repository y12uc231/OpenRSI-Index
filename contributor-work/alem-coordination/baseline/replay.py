"""Run all 20 native worlds once, using CPU Docker and unchanged official policy."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

from common import DEFAULT_WORK, ROOT, sha256, verify
from summarize import summarize


def command(work, output, image, name):
    return ['docker', 'run', '--rm', '--name', name, '--network', 'none',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--cpus', '4', '--memory', '6g', '--pids-limit', '256',
            '--tmpfs', '/tmp:rw,nosuid,size=1073741824',
            '-e', 'JAX_PLATFORM_NAME=cpu', '-e', 'WANDB_MODE=disabled',
            '-e', 'MPLCONFIGDIR=/tmp/matplotlib', '-e', 'XDG_CACHE_HOME=/tmp/cache',
            '-e', 'OMP_NUM_THREADS=4',
            '--mount', 'type=bind,src=' + str(work / 'source') + ',dst=/app,readonly',
            '--mount', 'type=bind,src=' + str(work / 'assets') + ',dst=/assets,readonly',
            '--mount', 'type=bind,src=' + str(ROOT / 'native20.py') + ',dst=/harness/native20.py,readonly',
            '--mount', 'type=bind,src=' + str(output) + ',dst=/results',
            '--workdir', '/tmp', image, 'python', '/harness/native20.py',
            '--episodes', '20', '--steps', '10000']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=DEFAULT_WORK)
    parser.add_argument('--image', default='openrsi-alem-native20:portable')
    parser.add_argument('--run-id', required=True, help='Unique label; existing output is never overwritten.')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', args.run_id):
        parser.error('run-id must be 1–64 letters, numbers, underscores or hyphens')
    work = args.work.resolve()
    verified = verify(work)
    details = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image]))[0]
    output = work / 'results' / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    name = 'alem-native20-' + args.run_id
    record = {**verified, 'status': 'running', 'image_id': details['Id'],
              'architecture': details['Architecture'], 'operator_timeout_seconds': 1800,
              'cpus': 4, 'memory_bytes': 6 * 1024**3, 'network': 'none',
              'training_calls': 0, 'llm_calls': 0,
              'harness_sha256': sha256(ROOT / 'native20.py'),
              'source_manifest_sha256': sha256(ROOT / 'source-manifest.json'),
              'asset_manifest_sha256': sha256(ROOT / 'asset-manifest.json'),
              'requirements_sha256': sha256(ROOT / 'requirements.lock')}
    launch = output / 'launch.json'
    launch.write_text(json.dumps(record, indent=2) + '\n')
    start = time.monotonic()
    try:
        with (output / 'stdout.txt').open('x') as stdout, (output / 'stderr.txt').open('x') as stderr:
            process = subprocess.run(command(work, output, details['Id'], name),
                                     stdout=stdout, stderr=stderr, timeout=1800)
        record['return_code'] = process.returncode
        record['status'] = 'completed' if process.returncode == 0 else 'infrastructure_or_incomplete'
        if record['status'] == 'completed':
            # A zero exit alone cannot establish that the complete batch exists.
            summarize(json.loads((output / 'result.json').read_text()))
    except subprocess.TimeoutExpired:
        record['status'] = 'operator_timeout'
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    except Exception as exc:
        record['status'] = 'infrastructure_or_incomplete'
        record['error_type'] = type(exc).__name__
    finally:
        record['wall_seconds'] = time.monotonic() - start
        try:
            verify(work)
            record['source_and_assets_unchanged'] = True
        except Exception:
            record['source_and_assets_unchanged'] = False
            record['status'] = 'provenance_failure'
        record['harness_unchanged'] = sha256(ROOT / 'native20.py') == record['harness_sha256']
        if not record['harness_unchanged']:
            record['status'] = 'provenance_failure'
        launch.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))
    if record['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()

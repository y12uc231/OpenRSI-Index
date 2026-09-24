"""Build a CPU image from verified source and the recorded dependency versions."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from common import DEFAULT_WORK, ROOT, sha256, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=DEFAULT_WORK)
    parser.add_argument('--image', default='openrsi-alem-native20:portable')
    args = parser.parse_args()
    work = args.work.resolve()
    verified = verify(work)
    # Build context excludes checkpoints, result logs, .git, and host directories.
    with tempfile.TemporaryDirectory(prefix='alem-build-') as folder:
        context = Path(folder)
        for name in ('Dockerfile', 'requirements.lock'):
            shutil.copyfile(ROOT / name, context / name)
        source = context / 'source'
        source.mkdir()
        for name in ('pyproject.toml', 'README.md', 'LICENSE'):
            shutil.copyfile(work / 'source' / name, source / name)
        shutil.copytree(work / 'source/alem', source / 'alem',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'texture_cache.pbz2'))
        subprocess.run(['docker', 'build', '-t', args.image, str(context)], check=True)
    details = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image]))[0]
    print(json.dumps({**verified, 'image_id': details['Id'], 'architecture': details['Architecture'],
                      'dockerfile_sha256': sha256(ROOT / 'Dockerfile'),
                      'requirements_sha256': sha256(ROOT / 'requirements.lock')}, indent=2))


if __name__ == '__main__':
    main()

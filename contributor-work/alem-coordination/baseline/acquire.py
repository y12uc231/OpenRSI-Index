"""Fetch exactly the pinned public source and one checkpoint, then verify bytes."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote
from urllib.request import urlopen

from common import DEFAULT_WORK, ROOT, checked_path, read_json, sha256, verify


def acquire(work):
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    source = work / 'source'
    spec = read_json(ROOT / 'source-manifest.json')
    if not source.exists():
        # Fetch/check out the immutable commit, not a moving branch or release tag.
        with tempfile.TemporaryDirectory(prefix='alem-source-', dir=work) as temporary:
            temporary = Path(temporary)
            subprocess.run(['git', 'init', '-q', str(temporary)], check=True)
            subprocess.run(['git', '-C', str(temporary), 'fetch', '--depth=1', spec['url'], spec['revision']], check=True)
            subprocess.run(['git', '-C', str(temporary), 'checkout', '-q', '--detach', 'FETCH_HEAD'], check=True)
            temporary.rename(source)
    assets = read_json(ROOT / 'asset-manifest.json')
    for entry in assets['files']:
        destination = checked_path(work, entry['path'])
        if destination.exists():
            if destination.stat().st_size != entry['bytes'] or sha256(destination) != entry['sha256']:
                raise ValueError('existing asset differs; refusing overwrite: ' + entry['path'])
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        hub_path = entry['path'].removeprefix('assets/')
        url = 'https://huggingface.co/' + assets['repo'] + '/resolve/' + assets['revision'] + '/' + quote(hub_path, safe='/')
        # Public artifact only: no authentication, user token, or credential forwarding.
        with tempfile.NamedTemporaryFile(prefix='download-', dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                with urlopen(url, timeout=120) as response:
                    copied = 0
                    while chunk := response.read(1024 * 1024):
                        copied += len(chunk)
                        if copied > entry['bytes']:
                            raise ValueError('asset exceeds declared byte count')
                        stream.write(chunk)
                stream.close()
                if temporary.stat().st_size != entry['bytes'] or sha256(temporary) != entry['sha256']:
                    raise ValueError('downloaded asset digest mismatch')
                temporary.rename(destination)
            finally:
                temporary.unlink(missing_ok=True)
    return verify(work)


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=DEFAULT_WORK)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify(args.work) if args.verify_only else acquire(args.work), indent=2))


if __name__ == '__main__':
    main()

"""Verify materialized public model assets offline; never download or execute."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def verify(directory, manifest):
    supplied = Path(directory)
    if supplied.is_symlink():
        raise ValueError('snapshot root must not be a symlink')
    root = supplied.resolve()
    if not root.is_dir() or root.name != manifest['revision']:
        raise ValueError('snapshot directory must use the manifest revision name')
    checked, size = set(), 0
    for record in manifest['files']:
        name = record['path']
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or not relative.parts or name in checked:
            raise ValueError('invalid or duplicate manifest path')
        path = root.joinpath(*relative.parts)
        if any(part.is_symlink() for part in [path, *list(path.parents)[:len(relative.parts)-1]]):
            raise ValueError('materialized regular files required: ' + name)
        if not path.is_file() or path.stat().st_size != record['bytes']:
            raise ValueError('asset size mismatch or missing file: ' + name)
        if record['algorithm'] == 'sha256':
            digest = hashlib.sha256()
        elif record['algorithm'] == 'git-blob-sha1':
            digest = hashlib.sha1()
            digest.update(b'blob ' + str(record['bytes']).encode() + b'\0')
        else:
            raise ValueError('unsupported manifest digest')
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != record['digest']:
            raise ValueError('asset hash mismatch: ' + name)
        checked.add(name)
        size += record['bytes']
    if not checked:
        raise ValueError('empty asset manifest')
    return {'revision': manifest['revision'], 'verified_files': len(checked), 'verified_bytes': size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('weights', type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name('qwen38-assets.json').read_text())
    print(json.dumps(verify(args.weights, manifest)))

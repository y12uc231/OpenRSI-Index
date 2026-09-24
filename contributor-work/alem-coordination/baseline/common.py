"""Portable provenance checks. This module never imports upstream model code."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parent
DEFAULT_WORK = ROOT / '.work'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def checked_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ('..', '.') for p in path.parts):
        raise ValueError('invalid relative manifest path')
    root = Path(root).resolve()
    target = root.joinpath(*path.parts)
    cursor = target
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError('manifest path must not contain symlinks')
        cursor = cursor.parent
    if not target.resolve().is_relative_to(root):
        raise ValueError('manifest path escapes work directory')
    return target


def verify(work):
    work = Path(work).resolve()
    source = work / 'source'
    spec = read_json(ROOT / 'source-manifest.json')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if head != spec['revision']:
        raise ValueError('upstream Git revision differs from manifest')
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=source).decode().split('\0')[:-1]
    if set(tracked) != set(spec['files']):
        raise ValueError('upstream tracked-file set differs from manifest')
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=source):
        raise ValueError('upstream checkout contains modified or untracked files')
    for name, expected in spec['files'].items():
        if sha256(checked_path(source, name)) != expected:
            raise ValueError('upstream source digest mismatch: ' + name)
    assets = read_json(ROOT / 'asset-manifest.json')
    for entry in assets['files']:
        path = checked_path(work, entry['path'])
        if path.stat().st_size != entry['bytes'] or sha256(path) != entry['sha256']:
            raise ValueError('checkpoint digest mismatch: ' + entry['path'])
    return {'source_revision': head, 'source_files': len(tracked),
            'asset_revision': assets['revision'], 'asset_files': len(assets['files']),
            'asset_bytes': assets['total_bytes']}

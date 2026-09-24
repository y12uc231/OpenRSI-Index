#!/usr/bin/env python3
"""Explicitly download, or verify, the public immutable model; no credentials."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent


def verify(path, item):
    if not path.is_file() or path.stat().st_size != item['size_bytes']:
        return False
    algorithm = item['digest_algorithm']
    digest = hashlib.sha256() if algorithm == 'sha256' else hashlib.sha1()
    if algorithm == 'git_blob_sha1':
        digest.update(f"blob {item['size_bytes']}\0".encode())
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest() == item['digest']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'model-artifacts-v1.json').read_text())
    root = args.destination.resolve()
    if not args.verify_only:
        root.mkdir(parents=True, exist_ok=True)
    for item in manifest['files']:
        path = root / item['path']
        if verify(path, item):
            print(f"verified {item['path']}", flush=True)
            continue
        if args.verify_only:
            raise SystemExit(f"Missing or mismatched artifact: {path}")
        if path.exists():
            raise SystemExit(f"Refusing to replace mismatched existing artifact: {path}")
        temporary = path.with_name(path.name + '.part')
        print(f"downloading {item['path']} ({item['size_bytes']} bytes)", flush=True)
        with urllib.request.urlopen(item['url'], timeout=120) as response, temporary.open('wb') as output:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                output.write(chunk)
        if not verify(temporary, item):
            raise SystemExit(f"Downloaded artifact failed integrity verification: {temporary}")
        temporary.replace(path)
    print(json.dumps({'verified': True, 'revision': manifest['revision'], 'directory': str(root)}))


if __name__ == '__main__':
    main()

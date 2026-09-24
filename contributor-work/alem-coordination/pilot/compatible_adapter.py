"""Prepared loopback-only open-model adapter; no GPU execution validated.

stdin JSON: {prompt, schema, metadata_path}; stdout: {response, metadata}.
This reuses the frozen LiveMigrate transport, changing only its task-specific
schema validator in a private module instance. No old transport file is edited.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

CONTRIBUTOR_WORK = Path(__file__).resolve().parents[2]
TRANSPORT = CONTRIBUTOR_WORK / 'livemigrate/pilot/compatible_adapter.py'
TRANSPORT_SHA256 = 'cd455842c6abccca0739cb052bf5f7e56e2e72ccea3d780c55242147ab946bad'
CONTROLLER_SCHEMA = {
    'type': 'object',
    'properties': {'controller': {'type': 'string'}, 'note': {'type': 'string'}},
    'required': ['controller', 'note'], 'additionalProperties': False,
}


def validate_schema(schema):
    if (not isinstance(schema, dict) or set(schema) != set(CONTROLLER_SCHEMA)
            or schema.get('type') != 'object'
            or schema.get('properties') != CONTROLLER_SCHEMA['properties']
            or schema.get('additionalProperties') is not False
            or not isinstance(schema.get('required'), list)
            or len(schema['required']) != 2
            or set(schema['required']) != {'controller', 'note'}):
        raise ValueError('exact required controller/note string schema expected')


def backend():
    if hashlib.sha256(TRANSPORT.read_bytes()).hexdigest() != TRANSPORT_SHA256:
        raise RuntimeError('reused transport differs from frozen SHA256')
    spec = importlib.util.spec_from_file_location('alem_private_compatible_transport', TRANSPORT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate_schema = validate_schema
    return module


def infer(packet, profile, transport=None, metadata=None):
    if metadata is None:
        metadata = {}
    started = time.monotonic()
    metadata.update({'status': 'invalid', 'usage': [], 'usage_complete': False,
                     'generation_requests_started': 0, 'automatic_retries': 0,
                     'adapter_scope': 'prepared open-model controller lane; GPU execution unvalidated',
                     'transport_sha256': TRANSPORT_SHA256,
                     'profile_canonical_sha256': hashlib.sha256(json.dumps(
                         profile, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()})
    try:
        if not isinstance(packet, dict) or not {'prompt', 'schema'} <= set(packet) or set(packet) - {'prompt', 'schema', 'metadata_path'}:
            raise ValueError('expected prompt/schema and optional metadata_path')
        validate_schema(packet['schema'])
        module = backend()
        result = module.infer(packet, profile, transport=transport or module.request, metadata=metadata)
        # The backend checks exactly one complete JSON object against this schema,
        # inclusive token counts/IDs, finish status, and absence of tool calls.
        return result
    except Exception as exc:
        metadata.update({'status': 'invalid', 'error_type': type(exc).__name__,
                         'seconds': round(time.monotonic() - started, 3)})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path, help='Pinned vLLM/Qwen-compatible launch profile JSON.')
    args = parser.parse_args(argv)
    module = backend()
    packet = module.decode(sys.stdin.read())
    metadata = {}
    metadata_path = packet.get('metadata_path') if isinstance(packet, dict) else None
    if metadata_path is not None and (not isinstance(metadata_path, str) or not metadata_path):
        raise ValueError('metadata_path must be a nonempty output path')
    status = 0
    try:
        raw_profile = args.profile.read_bytes()
        profile = module.decode(raw_profile.decode())
        metadata['profile_file_sha256'] = hashlib.sha256(raw_profile).hexdigest()
        result = infer(packet, profile, metadata=metadata)
    except Exception as exc:
        metadata.update({'status': 'invalid', 'error_type': type(exc).__name__})
        result = {'response': None, 'metadata': metadata}
        status = 1
    finally:
        if metadata_path is not None:
            # Path is provided by the trusted caller and never transmitted to vLLM.
            with Path(metadata_path).open('x') as stream:
                stream.write(json.dumps(metadata, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, allow_nan=False))
    return status


if __name__ == '__main__':
    raise SystemExit(main())

"""Provider-neutral inference transport. No shell, retries, or API client.

The caller explicitly opts into launching a locally supplied command. Credentials
are inherited from the environment and are never serialized by this adapter.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


SECRET_KEYS = {'api_key', 'apikey', 'access_token', 'authorization', 'password',
               'secret', 'token', 'credentials', 'headers', 'env'}


def _check_params(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in SECRET_KEYS:
                raise ValueError('Credentials belong in environment variables, not configuration.')
            _check_params(item)
    elif isinstance(value, list):
        for item in value:
            _check_params(item)


def validate_response(value, schema, location='$'):
    """Validate the object/array/string schema subset used by this pilot."""
    supported = {'type', 'properties', 'required', 'additionalProperties', 'items'}
    if set(schema) - supported:
        raise ValueError('Unsupported schema keyword; extend validation explicitly.')
    kind = schema.get('type')
    if kind == 'object':
        if not isinstance(value, dict):
            raise ValueError(f'{location}: expected object')
        properties = schema.get('properties', {})
        if set(schema.get('required', [])) - set(value):
            raise ValueError(f'{location}: missing required fields')
        if schema.get('additionalProperties') is False and set(value) - set(properties):
            raise ValueError(f'{location}: unexpected fields')
        for key, item in value.items():
            if key in properties:
                validate_response(item, properties[key], f'{location}.{key}')
    elif kind == 'array':
        if not isinstance(value, list):
            raise ValueError(f'{location}: expected array')
        for index, item in enumerate(value):
            validate_response(item, schema['items'], f'{location}[{index}]')
    elif kind == 'string':
        if not isinstance(value, str):
            raise ValueError(f'{location}: expected string')
    else:
        raise ValueError(f'Unsupported schema type: {kind}')


class CommandRunner:
    def __init__(self, config_path: Path):
        self.config_path = config_path.resolve()
        self.config_bytes = self.config_path.read_bytes()
        self.config = json.loads(self.config_bytes)
        allowed = {'model', 'command', 'params', 'timeout_seconds', 'execution_kind'}
        if set(self.config) - allowed:
            raise ValueError('Unknown configuration field.')
        self.model = self.config.get('model')
        if not isinstance(self.model, str) or not self.model:
            raise ValueError('A requested model identifier is required.')
        self.kind = self.config.get('execution_kind')
        if self.kind not in {'external_model', 'mock'}:
            raise ValueError('execution_kind must be external_model or mock.')
        argv = self.config.get('command')
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise ValueError('command must be a nonempty argv list; shell strings are unsupported.')
        self.command = [x.replace('{python}', sys.executable).replace(
            '{pilot_dir}', str(Path(__file__).resolve().parent)) for x in argv]
        self.params = self.config.get('params', {})
        if not isinstance(self.params, dict):
            raise ValueError('params must be an object.')
        _check_params(self.params)
        self.timeout = self.config.get('timeout_seconds', 480)
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)) or self.timeout <= 0:
            raise ValueError('timeout_seconds must be positive.')

    def infer(self, prompt: str, output_dir: Path, schema: dict) -> dict:
        output_dir.mkdir(parents=True, exist_ok=False)
        request = {'messages': [{'role': 'user', 'content': prompt}],
                   'schema': schema, 'model': self.model, 'params': self.params}
        request_text = json.dumps(request)
        (output_dir / 'request.json').write_text(json.dumps(request, indent=2) + '\n')
        (output_dir / 'prompt.txt').write_text(prompt)
        (output_dir / 'schema.json').write_text(json.dumps(schema, indent=2) + '\n')
        metadata = {'model_requested': self.model, 'execution_kind': self.kind,
                    'is_model_measurement': self.kind == 'external_model',
                    'config_sha256': hashlib.sha256(self.config_bytes).hexdigest(),
                    'request_sha256': hashlib.sha256(request_text.encode()).hexdigest(),
                    'attempt': 1, 'retries': 0, 'timeout_seconds': self.timeout,
                    'tool_free': 'wrapper_contract_only_not_independently_audited'}
        started = time.monotonic()
        stdout = stderr = ''
        try:
            result = subprocess.run(self.command, input=request_text, text=True,
                                    capture_output=True, timeout=self.timeout,
                                    cwd=output_dir, shell=False)
            stdout, stderr = result.stdout, result.stderr
            metadata['return_code'] = result.returncode
            if result.returncode != 0:
                raise ValueError('External command failed; see local logs.')
            envelope = json.loads(stdout)
            if not isinstance(envelope, dict) or set(envelope) != {'response', 'usage', 'model'}:
                raise ValueError('Expected exactly response, usage, and model in stdout JSON.')
            if not isinstance(envelope['usage'], dict):
                raise ValueError('usage must be an object; use {} when unavailable.')
            if not isinstance(envelope['model'], str) or not envelope['model']:
                raise ValueError('model must report an actual identifier or explicit unknown.')
            validate_response(envelope['response'], schema)
            metadata.update(status='completed', model_reported=envelope['model'],
                            model_identity_source='external_wrapper_report_not_independently_verified',
                            usage=envelope['usage'])
            (output_dir / 'response.json').write_text(json.dumps(envelope['response'], indent=2) + '\n')
            return envelope['response']
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout or ''
            stderr = error.stderr or ''
            metadata.update(status='timeout', error_kind='TimeoutExpired')
            raise RuntimeError('External command timed out; no retry was attempted.') from None
        except (ValueError, OSError) as error:
            metadata.update(status='invalid', error_kind=type(error).__name__)
            # Do not echo the command, provider output, or exception with possible credentials.
            raise RuntimeError('External command response invalid; inspect local artifacts.') from None
        finally:
            metadata['seconds'] = round(time.monotonic() - started, 3)
            for name, value in [('stdout.local.txt', stdout), ('stderr.local.txt', stderr)]:
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='replace')
                (output_dir / name).write_text(value)
            (output_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')


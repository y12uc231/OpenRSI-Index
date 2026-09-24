"""Strict, tool-free text adapter for the prepared local vLLM 0.10.2 lane.

No requests happen on import. ``infer`` deliberately requires the vLLM extensions
``/tokenize`` and ``return_token_ids``; it is not a generic paid-provider client.
The server uses the pinned native chat template, and input token IDs must match
between preflight and generation. Full generated IDs, including any reasoning
or control tokens, must equal inclusive completion usage. There are no retries.

Sources for the pinned protocol and inclusive generated-token accounting:
https://github.com/vllm-project/vllm/blob/v0.10.2/vllm/entrypoints/openai/protocol.py
https://github.com/vllm-project/vllm/blob/v0.10.2/vllm/entrypoints/openai/serving_tokenization.py
https://github.com/vllm-project/vllm/blob/v0.10.2/vllm/entrypoints/openai/serving_chat.py#L1280-L1303

The model revision is an expected launch-manifest identity, not remote attestation.
Use compute/serve.sh with verified artifacts. This module never downloads weights,
loads credentials, launches a server, executes a model action, or truncates context.
"""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'jointverify-qwen3-coder-30b'
REVISION = 'b2cff646eb4bb1d68355c01b18ae02e7cf42d120'
SERVER_VERSION = '0.10.2'
MAX_CONTEXT = 32768
MAX_OUTPUT = 4096
DEFAULT_ENDPOINT = 'http://127.0.0.1:8000/v1'
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
ACTION_KEYS = {'action', 'command', 'message', 'summary'}


class InferenceError(RuntimeError):
    """Fail closed; inspect local metadata to settle any consumed generation."""


class PreflightError(InferenceError):
    """No generation request was sent."""


class TokenLimitExceeded(PreflightError):
    """The declared context or shared token allowance cannot fit another call."""


def endpoint(value=None):
    """Only numeric loopback or localhost; no credentials, proxies or redirects."""
    value = value or os.environ.get('JOINTVERIFY_BASE_URL', DEFAULT_ENDPOINT)
    parts = urlsplit(value)
    if (parts.scheme not in {'http', 'https'} or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or parts.path.rstrip('/') != '/v1'):
        raise PreflightError('Endpoint must be an HTTP(S) loopback URL ending in /v1, without credentials/query/fragment')
    hostname = parts.hostname
    if hostname == 'localhost':
        hostname = '127.0.0.1'  # Do not trust external DNS or a proxy for localhost.
    try:
        address = ipaddress.ip_address(hostname or '')
        if not address.is_loopback:
            raise ValueError('not loopback')
        port = parts.port
    except ValueError as exc:
        raise PreflightError('Only a literal loopback address or localhost is allowed') from exc
    host = '[' + hostname + ']' if address.version == 6 else hostname
    netloc = host + (':' + str(port) if port is not None else '')
    return urlunsplit((parts.scheme, netloc, '/v1', '', ''))


def _integer(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0):
        raise InferenceError(name + ' must be a nonnegative integer' + (' greater than zero' if positive else ''))
    return value


def _ids(value, name):
    if not isinstance(value, list) or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in value):
        raise InferenceError(name + ' must contain integer token IDs')
    return value


def _decode_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise InferenceError('Duplicate JSON key: ' + key)
            result[key] = item
        return result
    def constant(value):
        raise InferenceError('Non-finite JSON constant: ' + value)
    return json.loads(value, object_pairs_hook=pairs, parse_constant=constant)


def _request_json(url, payload, *, deadline):
    """One HTTP request. http.client neither honors proxies nor follows redirects."""
    parts = urlsplit(url)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Inference deadline exhausted')
    connection_type = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
    connection = connection_type(parts.hostname, parts.port, timeout=remaining)
    data = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
    try:
        connection.request('GET' if payload is None else 'POST', parts.path, body=data,
                           headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        response = connection.getresponse()
        if response.status != 200:
            raise InferenceError('HTTP status ' + str(response.status) + '; request not retried')
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Inference deadline exhausted while reading response')
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            chunk = response.read1(min(65536, MAX_RESPONSE_BYTES - size + 1))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise InferenceError('Server response exceeds bounded local response size')
            chunks.append(chunk)
        return _decode_json(b''.join(chunks).decode('utf-8'))
    finally:
        connection.close()


def _schema_check(schema):
    expected = {'type': 'object', 'properties': {key: {'type': 'string'} for key in ACTION_KEYS},
                'required': sorted(ACTION_KEYS), 'additionalProperties': False}
    if not isinstance(schema, dict):
        raise PreflightError('Worker action schema must be an object')
    normalized = dict(schema)
    if isinstance(normalized.get('required'), list):
        normalized['required'] = sorted(normalized['required'])
    if normalized != expected:
        raise PreflightError('This frozen adapter accepts exactly the four-string JointVerify action schema')


def _action_check(action):
    if not isinstance(action, dict) or set(action) != ACTION_KEYS or any(not isinstance(v, str) for v in action.values()):
        raise InferenceError('Response does not match the strict action schema')
    if action['action'] not in {'shell', 'message', 'finish'}:
        raise InferenceError('Unknown worker action')
    if action['action'] == 'shell' and not action['command'].strip():
        raise InferenceError('Shell action has an empty command')
    if action['action'] != 'shell' and action['command']:
        raise InferenceError('Non-shell action has a command')
    return action


def _usage_check(response, tokenized):
    usage = response.get('usage')
    if not isinstance(usage, dict):
        raise InferenceError('Missing mandatory generation usage')
    prompt = _integer(usage.get('prompt_tokens'), 'prompt_tokens', positive=True)
    completion = _integer(usage.get('completion_tokens'), 'completion_tokens', positive=True)
    total = _integer(usage.get('total_tokens'), 'total_tokens', positive=True)
    if total != prompt + completion or completion > MAX_OUTPUT or total > MAX_CONTEXT:
        raise InferenceError('Usage totals or hard token limits disagree')
    if prompt != tokenized['count'] or _ids(response.get('prompt_token_ids'), 'prompt_token_ids') != tokenized['tokens']:
        raise InferenceError('Generation input differs from actual-template tokenization preflight')
    choices = response.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise InferenceError('Exactly one completion choice is required')
    if len(_ids(choices[0].get('token_ids'), 'completion token_ids')) != completion:
        raise InferenceError('Inclusive completion usage does not match all generated token IDs')
    normalized = {'input_tokens': prompt, 'output_tokens': completion, 'total_tokens': total}
    cached_details = usage.get('prompt_tokens_details')
    if cached_details is not None:
        if not isinstance(cached_details, dict):
            raise InferenceError('Malformed cached-token details')
        if cached_details.get('cached_tokens') is not None:
            cached = _integer(cached_details['cached_tokens'], 'cached_tokens')
            if cached > prompt:
                raise InferenceError('Cached tokens exceed inclusive input tokens')
            normalized['cached_input_tokens'] = cached
    reasoning_details = usage.get('completion_tokens_details')
    if reasoning_details is not None:
        if not isinstance(reasoning_details, dict):
            raise InferenceError('Malformed reasoning-token details')
        if reasoning_details.get('reasoning_tokens') is not None:
            reasoning = _integer(reasoning_details['reasoning_tokens'], 'reasoning_tokens')
            if reasoning > completion:
                raise InferenceError('Reasoning tokens exceed inclusive completion tokens')
            normalized['reasoning_tokens'] = reasoning
    return normalized


def infer(prompt: str, output_dir: Path, schema: dict, timeout: float = 480,
          *, base_url=None, remaining_tokens=None, seed=0, on_preflight=None) -> dict:
    """Return one validated action, preserving Codex-compatible local metadata.

    ``on_preflight(info)`` runs after exact tokenization and before generation,
    allowing the controller to reserve its shared ledger using input_upper_bound
    and output_token_limit. Its exception aborts generation. ``remaining_tokens``
    adds a per-call reservation gate; the caller owns the cross-call ledger.
    Always settle a started generation from metadata even when this raises.
    Missing usage makes the attempted call unscorable, never a free retry.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    metadata = {'status': 'invalid', 'return_code': 1, 'tool_free': True, 'usage': [],
                'model_requested': MODEL, 'model_revision_expected': REVISION,
                'server_version_expected': SERVER_VERSION, 'generation_requests_started': 0,
                'tokenization_requests_started': 0, 'automatic_retries': 0,
                'usage_complete': False, 'cached_input_counted_in_full': True,
                'output_accounting': 'All generated token IDs, including reasoning/control tokens; never visible-text retokenization.',
                'model_identity_source': 'Prepared pinned launch manifest; served alias and server version checked; not remote weight attestation.'}
    def write(name, value):
        (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    def event(kind, **details):
        with (output_dir / 'events.jsonl').open('a') as handle:
            handle.write(json.dumps({'type': kind, **details}, ensure_ascii=False, allow_nan=False) + '\n')
    try:
        if not isinstance(prompt, str) or not prompt:
            raise PreflightError('A nonempty text prompt is required')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise PreflightError('timeout must be a positive finite number')
        _schema_check(schema)
        _integer(seed, 'seed')
        if seed >= 2**63:
            raise PreflightError('seed must fit signed 64-bit range')
        if remaining_tokens is not None:
            _integer(remaining_tokens, 'remaining_tokens')
        base = endpoint(base_url)
        metadata['endpoint'] = base
        deadline = started + timeout
        (output_dir / 'prompt.txt').write_text(prompt)
        write('schema.json', schema)
        lane_path = ROOT / 'compute' / 'lane-v1.json'
        lane = json.loads(lane_path.read_text())
        if (lane['served_model_name'] != MODEL or lane['model_revision'] != REVISION
                or lane['runtime']['vllm_version'] != SERVER_VERSION
                or lane['runtime']['max_model_len'] != MAX_CONTEXT):
            raise PreflightError('Prepared compute lane no longer matches this frozen adapter')
        metadata['compute_lane_sha256'] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
        version = _request_json(base[:-3] + '/version', None, deadline=deadline)
        if not isinstance(version, dict) or version.get('version') != SERVER_VERSION:
            raise PreflightError('Server version differs from the frozen vLLM lane')
        metadata['server_version_observed'] = version['version']
        messages = [{'role': 'system', 'content': 'Return exactly one JSON object matching this schema. No direct model tools are available.\n' + json.dumps(schema, sort_keys=True)},
                    {'role': 'user', 'content': prompt}]
        template = {'model': MODEL, 'messages': messages, 'add_generation_prompt': True,
                    'continue_final_message': False, 'add_special_tokens': False}
        write('tokenize-request.json', template)
        metadata['tokenization_requests_started'] = 1
        event('tokenization.started')
        tokenized = _request_json(base[:-3] + '/tokenize', template, deadline=deadline)
        write('tokenize-response.json', tokenized)
        if not isinstance(tokenized, dict):
            raise PreflightError('Malformed tokenize response')
        count = _integer(tokenized.get('count'), 'tokenize count', positive=True)
        if len(_ids(tokenized.get('tokens'), 'tokenize tokens')) != count:
            raise PreflightError('Tokenize count and token IDs disagree')
        if tokenized.get('max_model_len') != MAX_CONTEXT:
            raise PreflightError('Server context configuration differs from the frozen lane')
        if count + MAX_OUTPUT > MAX_CONTEXT:
            raise TokenLimitExceeded('Context exceeds 32768 tokens after reserving all 4096 output tokens; no truncation permitted')
        if remaining_tokens is not None and count + MAX_OUTPUT > remaining_tokens:
            raise TokenLimitExceeded('Insufficient shared token allowance for input plus full output reservation')
        reservation = {'input_upper_bound': count, 'output_token_limit': MAX_OUTPUT,
                       'reservation_tokens': count + MAX_OUTPUT, 'context_limit': MAX_CONTEXT}
        metadata['preflight'] = reservation
        metadata['remaining_tokens_supplied'] = remaining_tokens
        event('tokenization.completed', **reservation)
        if on_preflight is not None:
            on_preflight(dict(reservation))
        request = dict(template, max_completion_tokens=MAX_OUTPUT, temperature=0.7, top_p=0.8,
                       top_k=20, repetition_penalty=1.05, stream=False, n=1, seed=seed,
                       response_format={'type': 'json_object'}, tool_choice='none',
                       return_token_ids=True, include_reasoning=True)
        write('request.json', request)
        metadata['generation_requests_started'] = 1
        event('turn.started', attempt=1)
        response = _request_json(base + '/chat/completions', request, deadline=deadline)
        write('server-response.json', response)
        if not isinstance(response, dict):
            raise InferenceError('Malformed chat response')
        usage = _usage_check(response, tokenized)
        metadata.update(usage=[usage], usage_complete=True, model_observed=response.get('model'))
        if response.get('model') != MODEL:
            raise InferenceError('Served model alias differs from frozen worker')
        choice = response['choices'][0]
        metadata['finish_reason'] = choice.get('finish_reason')
        message = choice.get('message')
        if not isinstance(message, dict) or message.get('role') != 'assistant':
            raise InferenceError('Missing assistant message')
        if message.get('tool_calls') or message.get('function_call'):
            metadata['tool_free'] = False
            raise InferenceError('Direct model tool call is forbidden')
        if message.get('refusal'):
            raise InferenceError('Model refusal')
        if choice.get('finish_reason') != 'stop':
            raise InferenceError('Truncated, refused or nonstandard completion termination')
        if not isinstance(message.get('content'), str):
            raise InferenceError('Missing text action content')
        action = _action_check(_decode_json(message['content']))
        write('response.json', action)
        metadata.update(status='completed', return_code=0)
        event('turn.completed', usage=usage)
        return action
    except Exception as exc:
        metadata.update(error_type=type(exc).__name__, error=str(exc))
        if isinstance(exc, TimeoutError):
            metadata['status'] = 'timeout'
        event('turn.failed', error_type=type(exc).__name__, error=str(exc),
              generation_requests_started=metadata['generation_requests_started'], usage=metadata['usage'])
        raise
    finally:
        metadata['seconds'] = round(time.monotonic() - started, 3)
        write('metadata.json', metadata)

"""Prepared, unexecuted vLLM transport for text-only model comparisons.

JSON stdin: {prompt, schema}; JSON stdout: {response, metadata}. No automatic
retries, credentials, downloads or paid-provider connections. Only loopback is
accepted. Exact native-template token IDs are checked against generation.
"""
from __future__ import annotations
import http.client
import ipaddress
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit


def decode(raw):
    def unique(pairs):
        answer = {}
        for key, value in pairs:
            if key in answer:
                raise ValueError('duplicate JSON key')
            answer[key] = value
        return answer
    def constant(value):
        raise ValueError('non-finite JSON number: ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=constant)


def origin(endpoint):
    parts = urlsplit(endpoint)
    if parts.scheme not in ('http', 'https') or parts.username or parts.password or parts.query or parts.fragment or parts.path.rstrip('/') != '/v1':
        raise ValueError('expected a credential-free loopback URL ending in /v1')
    host = '127.0.0.1' if parts.hostname == 'localhost' else parts.hostname
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError('remote endpoints are not enabled by this adapter')
    return parts.scheme, host, parts.port


def request(endpoint, path, payload, deadline):
    scheme, host, port = origin(endpoint)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('transport deadline')
    cls = http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection
    conn = cls(host, port, timeout=remaining)
    try:
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        conn.request('GET' if payload is None else 'POST', path, body=body,
                     headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        response = conn.getresponse()
        if response.status != 200:
            raise RuntimeError('HTTP status %s; no automatic retry' % response.status)
        chunks, count = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('response deadline')
            if conn.sock is not None:
                conn.sock.settimeout(remaining)
            block = response.read1(min(65536, 4 * 1024 * 1024 - count + 1))
            if not block:
                break
            chunks.append(block)
            count += len(block)
            if count > 4 * 1024 * 1024:
                raise RuntimeError('response too large')
        return decode(b''.join(chunks).decode())
    finally:
        conn.close()


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('invalid ' + name)
    return value


def ids(value):
    if not isinstance(value, list) or any(type(x) is not int or x < 0 for x in value):
        raise ValueError('invalid token IDs')
    return value


def validate_schema(schema):
    if not isinstance(schema, dict) or schema.get('type') != 'object' or schema.get('additionalProperties') is not False:
        raise ValueError('strict object schema required')
    properties = schema.get('properties', {})
    if not properties or set(schema.get('required', [])) != set(properties) or any(value != {'type': 'string'} for value in properties.values()):
        raise ValueError('required string fields expected')
    if not set(properties).issubset({'db', 'api', 'consumer', 'message'}):
        raise ValueError('unexpected output field')


def infer(packet, profile, transport=request, metadata=None):
    started = time.monotonic()
    if metadata is None:
        metadata = {}
    metadata.update({'status': 'invalid', 'usage': [], 'usage_complete': False,
                     'generation_requests_started': 0, 'automatic_retries': 0,
                     'model_requested': profile['model_id'],
                     'model_revision_expected': profile['model_revision'],
                     'model_identity_source': 'pinned launch profile; alias/version checked, no remote weight attestation',
                     'reasoning_effort': 'xhigh', 'vllm_version': profile['vllm_version']})
    validate_schema(packet['schema'])
    if not isinstance(packet['prompt'], str) or not packet['prompt']:
        raise ValueError('empty prompt')
    endpoint = profile['endpoint']
    origin(endpoint)
    deadline = started + profile.get('transport_timeout_seconds', 1800)
    model = profile['served_model_name']
    version = transport(endpoint, '/version', None, deadline)
    if version.get('version') != profile['vllm_version']:
        raise RuntimeError('serving version does not match the frozen profile')
    listed = transport(endpoint, '/v1/models', None, deadline)
    if model not in {row.get('id') for row in listed.get('data', [])}:
        raise RuntimeError('requested model alias is not served')
    messages = [{'role': 'user', 'content': packet['prompt']}]
    template = {'enable_thinking': True, 'preserve_thinking': True, 'reasoning_effort': 'xhigh'}
    tokenized = transport(endpoint, '/tokenize', {
        'model': model, 'messages': messages, 'add_generation_prompt': True,
        'add_special_tokens': False, 'chat_template_kwargs': template}, deadline)
    count = integer(tokenized.get('count'), 'token count', 1)
    prompt_ids = ids(tokenized.get('tokens'))
    output_cap = integer(profile['max_completion_tokens'], 'completion cap', 1)
    context_cap = integer(profile['max_model_len'], 'context cap', 1)
    if count != len(prompt_ids) or count + output_cap > context_cap:
        raise RuntimeError('context reservation does not fit; no truncation or generation')
    if integer(tokenized.get('max_model_len'), 'server context', 1) < context_cap:
        raise RuntimeError('server context is smaller than frozen profile')
    payload = {
        'model': model, 'messages': messages, 'n': 1, 'stream': False,
        'temperature': 1.0, 'top_p': 0.95, 'top_k': 20, 'min_p': 0.0,
        'presence_penalty': 0.0, 'repetition_penalty': 1.0,
        'seed': profile['seed'], 'max_completion_tokens': output_cap,
        'reasoning_effort': 'xhigh', 'chat_template_kwargs': template,
        'return_token_ids': True,
        'response_format': {'type': 'json_schema', 'json_schema': {
            'name': 'migration_sources', 'strict': True, 'schema': packet['schema']}},
    }
    metadata['generation_requests_started'] = 1
    response = transport(endpoint, '/v1/chat/completions', payload, deadline)
    usage = response.get('usage', {})
    metadata['raw_reported_usage'] = {key: value for key, value in usage.items()
                                      if type(value) is int and value >= 0}
    incoming = integer(usage.get('prompt_tokens'), 'input tokens', 1)
    outgoing = integer(usage.get('completion_tokens'), 'output tokens', 1)
    total = integer(usage.get('total_tokens'), 'total tokens', 1)
    if total == incoming + outgoing:
        metadata['usage'] = [{'input_tokens': incoming, 'output_tokens': outgoing, 'total_tokens': total}]
        metadata['usage_reported_complete'] = True
    choices = response.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        raise RuntimeError('exactly one completion required')
    choice = choices[0]
    if incoming != count or ids(response.get('prompt_token_ids')) != prompt_ids:
        raise RuntimeError('generation prompt differs from tokenization preflight')
    if len(ids(choice.get('token_ids'))) != outgoing or outgoing > output_cap or total != incoming + outgoing or total > context_cap:
        raise RuntimeError('inclusive generation-token accounting mismatch')
    metadata['usage_complete'] = True
    message = choice.get('message', {})
    metadata['all_generated_token_ids_counted'] = True
    if choice.get('finish_reason') != 'stop' or message.get('tool_calls') or message.get('refusal'):
        raise RuntimeError('incomplete or unexpected tool completion; no retry')
    result = decode(message['content'])
    if not isinstance(result, dict) or set(result) != set(packet['schema']['properties']) or any(not isinstance(value, str) for value in result.values()):
        raise RuntimeError('invalid source object; no replacement generation')
    normalized = {'input_tokens': incoming, 'output_tokens': outgoing, 'total_tokens': total}
    cached = usage.get('prompt_tokens_details') or {}
    if cached.get('cached_tokens') is not None:
        value = integer(cached['cached_tokens'], 'cached tokens')
        if value > incoming:
            raise RuntimeError('cached tokens exceed input')
        normalized['cached_input_tokens'] = value
    metadata.update({'status': 'completed', 'seconds': round(time.monotonic() - started, 3),
                     'usage': [normalized]})
    return {'response': result, 'metadata': metadata}


if __name__ == '__main__':
    profile = decode(Path(sys.argv[1]).read_text())
    packet = decode(sys.stdin.read())
    metadata = {}
    try:
        print(json.dumps(infer(packet, profile, metadata=metadata), allow_nan=False))
    except Exception as exc:
        metadata.update({'status': 'invalid', 'error_type': type(exc).__name__})
        raise
    finally:
        if packet.get('metadata_path'):
            Path(packet['metadata_path']).write_text(json.dumps(metadata, indent=2, allow_nan=False) + '\n')

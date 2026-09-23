"""Single-request, stdlib-only Chat Completions command transport.

Preparation does not execute this file. Running it can incur provider charges.
Endpoint/key are read only from RELAYREPAIR_BASE_URL / RELAYREPAIR_API_KEY.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from command_runner import validate_response

PARAMS = {'temperature', 'top_p', 'seed', 'max_tokens', 'max_completion_tokens',
          'reasoning_effort', 'frequency_penalty', 'presence_penalty'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        # Returning None makes urllib reject redirects rather than forward auth.
        return None


def complete(request, environ=None, opener=None):
    environ = os.environ if environ is None else environ
    base = environ.get('RELAYREPAIR_BASE_URL', '').rstrip('/')
    if not base:
        raise ValueError('RELAYREPAIR_BASE_URL must be set explicitly; there is no default endpoint.')
    parsed = urlsplit(base)
    local = parsed.hostname in {'localhost', '127.0.0.1', '::1'}
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.scheme not in {'http', 'https'} or (parsed.scheme == 'http' and not local)):
        raise ValueError('Base URL must be HTTPS, or loopback HTTP, without credentials, query, or fragment.')
    key = environ.get('RELAYREPAIR_API_KEY', '')
    if not key and not local:
        raise ValueError('RELAYREPAIR_API_KEY is required for a remote endpoint.')
    if '\n' in key or '\r' in key:
        raise ValueError('Invalid credential format.')
    if not isinstance(request, dict) or set(request) != {'messages', 'schema', 'model', 'params'}:
        raise ValueError('Expected messages, schema, model, and params.')
    if not isinstance(request['model'], str) or not request['model']:
        raise ValueError('Requested model identifier is required.')
    if request['model'].startswith('YOUR_'):
        raise ValueError('Replace the example model placeholder before execution.')
    messages = request['messages']
    if not isinstance(messages, list) or not messages:
        raise ValueError('messages must be a nonempty list.')
    for message in messages:
        if (not isinstance(message, dict) or set(message) != {'role', 'content'}
                or message['role'] not in {'system', 'developer', 'user', 'assistant'}
                or not isinstance(message['content'], str)):
            raise ValueError('Only explicit text messages without tool fields are supported.')
    params = request['params']
    if not isinstance(params, dict) or set(params) - PARAMS:
        raise ValueError('Unsupported parameter override; model, messages, tools, routing, and credentials are fixed.')
    if 'max_tokens' in params and 'max_completion_tokens' in params:
        raise ValueError('Choose one supported completion-limit parameter.')
    if any(isinstance(v, (dict, list)) for v in params.values()):
        raise ValueError('Only scalar inference parameters are supported.')
    body = {'messages': messages, 'model': request['model'], 'stream': False, 'n': 1,
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'relayrepair_response', 'strict': True, 'schema': request['schema']}},
            **params}
    if parsed.hostname == 'openrouter.ai':
        body['provider'] = {'require_parameters': True, 'allow_fallbacks': False}
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    http_request = Request(base + '/chat/completions', data=json.dumps(body).encode(),
                           headers=headers, method='POST')
    opener = build_opener(NoRedirect()) if opener is None else opener
    try:
        # Exactly one application request. No SDK retries, redirect following, or healing.
        with opener.open(http_request, timeout=450) as response:
            if response.status != 200:
                raise ValueError('Non-successful HTTP status.')
            payload = json.load(response)
    except HTTPError as error:
        raise ValueError(f'HTTP {error.code}; no retry or redirect attempted.') from None
    except (URLError, TimeoutError, OSError):
        raise ValueError('Transport failure; no retry attempted.') from None
    if not isinstance(payload, dict) or payload.get('error'):
        raise ValueError('Provider returned an error envelope.')
    choices = payload.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError('Exactly one response choice is required.')
    choice = choices[0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Completion was truncated, filtered, tool-directed, or otherwise unfinished.')
    message = choice.get('message', {})
    if message.get('tool_calls') or message.get('function_call') or message.get('refusal'):
        raise ValueError('Tool output or refusal is invalid for this tool-free pilot.')
    content = message.get('content')
    if not isinstance(content, str):
        raise ValueError('Expected text JSON content.')
    result = json.loads(content)
    validate_response(result, request['schema'])
    model = payload.get('model')
    if not isinstance(model, str) or not model:
        raise ValueError('Provider did not report its model identifier.')
    usage = payload.get('usage') or {}
    if not isinstance(usage, dict):
        raise ValueError('Invalid usage object.')
    return {'response': result, 'usage': usage, 'model': model}


def main():
    try:
        result = complete(json.load(sys.stdin))
        json.dump(result, sys.stdout)
        sys.stdout.write('\n')
    except Exception as error:
        # Never emit headers, credentials, provider error bodies, endpoint URLs,
        # request payloads, or arbitrary exception text to diagnostic logs.
        print(f'Compatible transport failed ({type(error).__name__}); no retry attempted.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

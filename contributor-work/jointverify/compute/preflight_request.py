#!/usr/bin/env python3
"""Count the pinned native chat template, reserve tokens, and prepare chat JSON."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

MODEL_ALIAS = 'jointverify-qwen3-coder-30b'
MAX_CONTEXT = 32768
MAX_OUTPUT = 4096


def prepare(request, tokenizer, *, remaining_tokens, max_context=MAX_CONTEXT):
    if not isinstance(request, dict) or not isinstance(request.get('messages'), list) or not request['messages']:
        raise ValueError('A nonempty messages list is required.')
    allowed = {'messages', 'model', 'response_format', 'seed'}
    if set(request) - allowed:
        raise ValueError('Request contains uncontrolled fields; the controller fixes generation and template settings.')
    if request.get('model', MODEL_ALIAS) != MODEL_ALIAS:
        raise ValueError('The frozen model alias cannot be changed.')
    for message in request['messages']:
        if (not isinstance(message, dict) or set(message) != {'role', 'content'}
                or message['role'] not in {'system', 'user', 'assistant'}
                or not isinstance(message['content'], str)):
            raise ValueError('Only text system/user/assistant messages are supported; no native tools.')
    if request['messages'][-1]['role'] != 'user':
        raise ValueError('The controller must finish each request with a user observation.')
    if isinstance(remaining_tokens, bool) or not isinstance(remaining_tokens, int) or remaining_tokens < 0:
        raise ValueError('remaining_tokens must be a nonnegative integer.')
    if 'response_format' in request and request['response_format'] != {'type': 'json_object'}:
        raise ValueError('Only the same optional JSON-object output constraint is permitted in every arm.')
    # Tokenize the exact server-side native template, including assistant prefix.
    ids = tokenizer.apply_chat_template(request['messages'], tokenize=True, add_generation_prompt=True)
    prompt_tokens = len(ids)
    reservation = prompt_tokens + MAX_OUTPUT
    if reservation > max_context:
        raise ValueError(f'Context does not fit: {prompt_tokens} prompt + {MAX_OUTPUT} output > {max_context}.')
    if reservation > remaining_tokens:
        raise ValueError('Insufficient remaining shared tokens; submit the current patches instead of issuing a call.')
    payload = dict(request)
    payload.update(model=MODEL_ALIAS, max_completion_tokens=MAX_OUTPUT, temperature=0.7,
                   top_p=0.8, top_k=20, repetition_penalty=1.05, stream=False)
    return {'request': payload, 'prompt_tokens': prompt_tokens, 'output_token_limit': MAX_OUTPUT,
            'reservation_tokens': reservation, 'context_limit': max_context}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-directory', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--remaining-tokens', type=int, required=True)
    args = parser.parse_args()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.model_directory.resolve()),
                                               local_files_only=True, trust_remote_code=False)
    result = prepare(json.loads(args.request.read_text()), tokenizer, remaining_tokens=args.remaining_tokens)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

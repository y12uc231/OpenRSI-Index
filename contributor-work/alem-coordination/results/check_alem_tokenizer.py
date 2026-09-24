"""Offline context planning only: no GPU, weights, inference, or endpoint.

Install transformers==4.57.1 and jinja2==3.1.6 in a separate environment.
This check does not replace the prepared adapter's live vLLM preflight.
"""
import argparse
import hashlib
import json
from pathlib import Path

import tokenizers
import transformers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tokenizer', required=True, type=Path)
    parser.add_argument('--asset-manifest', required=True, type=Path)
    parser.add_argument('--pilot-runs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.asset_manifest.read_text())
    files = {}
    for entry in manifest['files']:
        if entry['path'] not in {'config.json', 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'}:
            continue
        raw = (args.tokenizer / entry['path']).read_bytes()
        measured = (hashlib.sha256(raw).hexdigest() if entry['algorithm'] == 'sha256' else
                    hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest())
        assert measured == entry['digest'] and len(raw) == entry['bytes']
        files[entry['path']] = hashlib.sha256(raw).hexdigest()
    tok = transformers.AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True, trust_remote_code=False)
    rows = []
    for path in sorted(args.pilot_runs.glob('*/call-*/prompt.txt')):
        prompt = path.read_text()
        ids = tok.apply_chat_template([{'role': 'user', 'content': prompt}], tokenize=True,
                                      add_generation_prompt=True, enable_thinking=True,
                                      preserve_thinking=True, reasoning_effort='xhigh')
        rows.append({'input_artifact': str(path.relative_to(args.pilot_runs)),
                     'prompt_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'prompt_tokens_offline': len(ids), 'max_completion_tokens': 32768,
                     'max_model_len': 65536, 'fits_full_reservation_offline': len(ids) + 32768 <= 65536})
    report = {'scope': 'CPU-only template/tokenizer planning check; no weights, inference, serving endpoint or GPU; not required live vLLM preflight',
              'model_id': manifest['model_id'], 'model_revision': manifest['revision'],
              'transformers': transformers.__version__, 'tokenizers': tokenizers.__version__,
              'artifact_sha256': files, 'prompts': rows}
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

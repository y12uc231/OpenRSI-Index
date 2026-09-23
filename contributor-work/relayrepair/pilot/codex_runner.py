"""Small, auditable Codex CLI inference adapter. No tools, no shared agent history.

Uses the explicitly recorded locally configured model, not a claimed multi-model
benchmark. Raw events are audited: any non-message item invalidates the call.
"""
from __future__ import annotations
import json
import subprocess
import tempfile
import time
from pathlib import Path

MODEL = 'gpt-6-astra'
EFFORT = 'ultra'


def infer(prompt: str, output_dir: Path, schema: dict, timeout: int = 480) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    schema_path = output_dir / 'schema.json'
    schema_path.write_text(json.dumps(schema, indent=2) + '\n')
    (output_dir / 'prompt.txt').write_text(prompt)
    with tempfile.TemporaryDirectory(prefix='relayrepair-context-') as task_dir:
        cmd = ['codex', 'exec', '--ephemeral', '--ignore-user-config',
               '--skip-git-repo-check', '--sandbox', 'read-only',
               '--disable', 'shell_tool', '--disable', 'multi_agent',
               '--disable', 'plugins', '--disable', 'apps',
               '--disable', 'browser_use', '--disable', 'computer_use',
               '-c', f'model="{MODEL}"', '-c', f'model_reasoning_effort="{EFFORT}"',
               '-c', 'web_search="disabled"', '-C', task_dir, '--json',
               '--output-schema', str(schema_path.resolve()),
               '-o', str((output_dir / 'response.json').resolve()), '-']
        t0 = time.monotonic()
        try:
            p = subprocess.run(cmd, input=prompt, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            for name, data in [('events.partial.jsonl', exc.stdout), ('stderr.partial.local.txt', exc.stderr)]:
                if isinstance(data, bytes):
                    data = data.decode('utf-8', errors='replace')
                (output_dir / name).write_text(data or '')
            (output_dir / 'metadata.json').write_text(json.dumps({'status':'timeout', 'seconds':time.monotonic()-t0}))
            raise
    (output_dir / 'events.jsonl').write_text(p.stdout)
    # Full local stderr may contain local paths. It is not included in public artifacts.
    (output_dir / 'stderr.local.txt').write_text(p.stderr)
    events = [json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
    bad = [e for e in events if e.get('type', '').startswith('item.') and
           e.get('item', {}).get('type') not in ('agent_message', 'reasoning')]
    usage = [e['usage'] for e in events if e.get('type') == 'turn.completed']
    finished = len(usage) == 1 and not any(e.get('type') in ('turn.failed', 'error') for e in events)
    metadata = {'model_requested': MODEL, 'reasoning_effort': EFFORT,
                'model_identity_source':'local user configuration; CLI requested identifier; no server snapshot ID exposed',
                'return_code':p.returncode, 'seconds':round(time.monotonic()-t0,3),
                'tool_free':not bool(bad), 'usage':usage,
                'status':'completed' if p.returncode == 0 and not bad and finished else 'invalid'}
    (output_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    if p.returncode != 0 or bad or not finished:
        raise RuntimeError(f'Invalid inference call: {metadata}')
    return json.loads((output_dir / 'response.json').read_text())


def batch_schema(field: str) -> dict:
    props = {'case_id': {'type':'string'}, field: {'type':'string'}}
    return {'type':'object','properties':{'results':{'type':'array','items':{
        'type':'object','properties':props,'required':list(props),'additionalProperties':False}}},
        'required':['results'],'additionalProperties':False}

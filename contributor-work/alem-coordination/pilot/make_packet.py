"""Build an explicit public source packet; never import upstream game code."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


def selected_definitions(path: Path, wanted: set[str]) -> str:
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted:
            found[node.name] = ''.join(lines[node.lineno - 1:node.end_lineno])
    if set(found) != wanted:
        raise ValueError('Missing source definitions: ' + str(wanted - set(found)))
    return '\n\n'.join(found[name] for name in sorted(found))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = args.source.resolve()
    source_manifest = json.loads((root / 'baseline/source-manifest.json').read_text())['files']
    selected_paths = ['SYSTEM_PROMPT.md', 'alem/alem_coop/renderer/renderer_symbolic.py',
                      'alem/alem_coop/action_masking.py', 'alem/alem_coop/constants.py',
                      'alem/alem_coop/game_logic.py']
    for name in selected_paths:
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != source_manifest[name]:
            raise ValueError('Public source differs from pinned upstream: ' + name)
    files = {
        'controller/CONTRACT.md': args.contract.read_text(),
        'TASK_DESIGN.md': (root / 'TASK_DESIGN.md').read_text(),
        'upstream/SYSTEM_PROMPT.md': (source / 'SYSTEM_PROMPT.md').read_text(),
        'upstream/renderer_symbolic.py': (source / 'alem/alem_coop/renderer/renderer_symbolic.py').read_text(),
        'upstream/action_masking.py': (source / 'alem/alem_coop/action_masking.py').read_text(),
        'upstream/constants.selected.py': selected_definitions(
            source / 'alem/alem_coop/constants.py', {'Action', 'BlockType', 'ItemType', 'Specialization'}),
        'upstream/coordination.selected.py': selected_definitions(
            source / 'alem/alem_coop/game_logic.py', {
                'check_sync_coordination', 'clear_completed_handovers',
                'add_pending_handovers', 'process_handover', 'do_construction',
                'process_communication'}),
    }
    # Literal official map dimensions are verified from its AST, not inferred.
    tree = ast.parse((source / 'alem/alem_coop/constants.py').read_text())
    obs = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'OBS_DIM' for t in n.targets))
    assert obs == (9, 11)
    files['upstream/observation-note.txt'] = (
        'Official OBS_DIM=(9,11), row-major spatial flattening. The appended self-ID '
        'has 3 values. The vector has 9733 floats and the mask 60 actions for this '
        'checkpoint. Spatial channels per tile: blocks 0:42, items 42:47, mobs '
        '47:87, teammate identity 87:90, alive 90, coordination value 91, '
        'soft flag 92, mob coordination 93:95, active handover time 95, light 96. '
        'Spatial shape (9,11,97) occupies the first 9603 values. '
        'DIRECTIONS for actions 0..4 are [(0,0),(0,-1),(0,1),(-1,0),(1,0)]; '
        'CLOSE_BLOCKS also includes four diagonal offsets. '
        'Use renderer_symbolic.py and action_masking.py for exact '
        'layout/semantics. These are public upstream source excerpts, not an '
        'extra observation or simulator service. Candidate runtime has Python '
        'standard library only. Four communication actions follow native GIVE '
        'recipient expansion; use schema.native_comm_action_ids, not guessed IDs. '
        'SYSTEM_PROMPT is an upstream example, including a specific agent/role; '
        'your actual agent_id and observed specialization govern each of your '
        'three separate controller instances.\n')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for name, body in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        manifest[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'files': len(files), 'characters': sum(map(len, files.values())),
                      'manifest_sha256': hashlib.sha256((out / 'MANIFEST.json').read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()

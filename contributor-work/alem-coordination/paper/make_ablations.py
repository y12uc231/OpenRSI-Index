"""Append predeclared diagnostic wrappers without executing candidate source."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

MODES = ('reset_explicit_json_memory', 'suppress_controller_added_comm')
PREFIX = '_alem_paper_'
MARKER = 'ALEM_PAPER_ADDED_COMM_SUPPRESSED_V1'
COMMON = r'''
# Predeclared paper diagnostic wrapper; this source is a separate candidate.
import json as _alem_paper_json
import sys as _alem_paper_sys
_alem_paper_original_initialize = initialize
_alem_paper_original_act = act
_alem_paper_initial = None
_alem_paper_comm = ()

def initialize(agent_id, schema):
    global _alem_paper_initial, _alem_paper_comm
    value = _alem_paper_original_initialize(agent_id, schema)
    _alem_paper_initial = _alem_paper_json.dumps(value, allow_nan=False, separators=(',', ':'))
    _alem_paper_comm = tuple(schema['native_comm_action_ids'])
    return value
'''
RESET = r'''
def act(local, memory):
    initial = _alem_paper_json.loads(_alem_paper_initial)
    # The unchanged trusted driver still validates the returned memory.
    return _alem_paper_original_act(local, initial)
'''
SUPPRESS = r'''
def act(local, memory):
    response = _alem_paper_original_act(local, memory)
    # Do not accidentally repair an invalid original response.
    if not isinstance(response, dict) or set(response) != {'action', 'memory'}:
        raise ValueError('original result schema')
    action = response['action']
    mask = local['legal_mask']
    if type(action) is not int or not 0 <= action < len(mask) or not mask[action]:
        raise ValueError('original action invalid')
    if action in _alem_paper_comm and action != local['proposal']:
        print('ALEM_PAPER_ADDED_COMM_SUPPRESSED_V1', file=_alem_paper_sys.stderr)
        return {'action': local['proposal'], 'memory': response['memory']}
    return response
'''


def wrapped(source, mode):
    if mode not in MODES:raise ValueError('unknown intervention')
    if PREFIX in source or MARKER in source:
        raise ValueError('candidate uses reserved diagnostic names')
    ast.parse(source)  # Parse only; never import or execute generated code here.
    return source + '\n' + COMMON + (RESET if mode == MODES[0] else SUPPRESS)


def build(source_path, output, mode):
    source_path, output = Path(source_path), Path(output)
    source = source_path.read_bytes()
    result = wrapped(source.decode('utf-8'),mode).encode('utf-8')
    output.mkdir(parents=True,exist_ok=False)
    (output/'controller.py').write_bytes(result)
    metadata = {'intervention':mode,'original_sha256':hashlib.sha256(source).hexdigest(),
                'wrapped_sha256':hashlib.sha256(result).hexdigest(),
                'wrapper_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/'intervention.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=MODES,required=True)
    a=p.parse_args();print(json.dumps(build(a.source,a.output,a.mode)))

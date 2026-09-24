"""Frozen 4+16 seed pack, generated without candidate inputs or score selection."""
import copy
import base_scenarios
from schedule_policy import config

TEMPLATES = base_scenarios.PUBLIC + base_scenarios.HELDOUT

def make_case(index):
    c = config(index)
    result = copy.deepcopy(TEMPLATES[c['template_index']])
    result['name'] = f"{c['split']}_{index:02d}__{result['name']}"
    result['schedule_audit'] = c
    return result

PUBLIC = [make_case(i) for i in range(4)]
HELDOUT = [make_case(i) for i in range(4,20)]

def suite(name):
    if name not in ('public','heldout','all'):
        raise ValueError('unknown suite')
    return copy.deepcopy(PUBLIC if name == 'public' else HELDOUT if name == 'heldout' else PUBLIC + HELDOUT)

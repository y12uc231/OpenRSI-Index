"""Declarative coordination policy; no candidate controller code is executed."""
from __future__ import annotations
import json
from pathlib import Path

ROLES = ('db', 'api', 'consumer')


def validate(value):
    if not isinstance(value, dict) or set(value) != {'version', 'shared_instruction', 'role_instructions', 'stages'}:
        raise ValueError('Scaffold requires exactly version, shared_instruction, role_instructions, stages')
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported scaffold version')
    instructions = value['role_instructions']
    if not isinstance(instructions, dict) or set(instructions) != set(ROLES):
        raise ValueError('Exactly three role instructions required')
    texts = [value['shared_instruction']] + list(instructions.values())
    if any(not isinstance(t, str) for t in texts) or sum(len(t) for t in texts) > 5000:
        raise ValueError('Instructions must be strings totaling at most 5000 characters')
    stages = value['stages']
    if not isinstance(stages, list) or len(stages) != 2:
        raise ValueError('Exactly two stages required')
    for stage in stages:
        if not isinstance(stage, list) or not 1 <= len(stage) <= 3:
            raise ValueError('A stage contains one to three waves')
        roles = []
        for wave in stage:
            if not isinstance(wave, list) or not wave or any(type(r) is not str or r not in ROLES for r in wave):
                raise ValueError('A wave contains named roles')
            roles.extend(wave)
        if sorted(roles) != sorted(ROLES):
            raise ValueError('Each stage must call each role exactly once')
    return value


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate scaffold key')
            result[key] = value
        return result
    data = Path(path).read_bytes()
    if len(data) > 32768:
        raise ValueError('Scaffold file too large')
    return validate(json.loads(data, object_pairs_hook=unique))

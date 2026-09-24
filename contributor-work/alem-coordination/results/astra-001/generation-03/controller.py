"""Deterministic frozen-policy pass-through controller."""


def initialize(agent_id, schema):
    return {}


def act(local, memory):
    return {"action": local["proposal"], "memory": memory}

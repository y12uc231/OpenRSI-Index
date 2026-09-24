"""Exact frozen-policy pass-through for the development comparison."""


def initialize(agent_id, schema):
    return {}


def act(local, memory):
    return {"action": local["proposal"], "memory": memory}

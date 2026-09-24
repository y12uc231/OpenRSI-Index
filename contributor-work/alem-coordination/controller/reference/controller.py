"""Trusted pass-through: use the frozen official masked-mode proposal."""
def initialize(agent_id, schema):
    return {'agent_id':agent_id, 'calls':0}

def act(local, memory):
    memory['calls']+=1
    return {'action':local['proposal'],'memory':memory}

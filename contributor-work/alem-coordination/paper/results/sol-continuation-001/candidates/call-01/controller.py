H, W, C = 9, 11, 97
SPATIAL = H * W * C
INTRINSICS = SPATIAL + 54 + 24 + 16 + 6
DIRECTION = INTRINSICS + 8
PASSABLE = {0, 1, 2, 6, 7, 13, 25, 26, 27, 41}
BUILD_ACTIONS = (53, 52, 51)


def initialize(agent_id, schema):
    return {'id': int(agent_id), 'focus': None, 'phase': 0, 'cool': []}


def _base(r, c):
    return (r * W + c) * C


def _block(obs, p):
    for kind in range(42):
        if obs[p + kind] > 0.5:
            return kind
    return -1


def _mob(obs, p):
    for kind in range(40):
        if obs[p + 47 + kind] > 0.5:
            return kind
    return -1


def _scan(obs, agent_id):
    positions = {agent_id: (4, 5)}
    others = [i for i in range(3) if i != agent_id]
    cells = []
    active = []
    for r in range(H):
        for c in range(W):
            p = _base(r, c)
            if obs[p + 96] < 0.5:
                continue
            for slot, peer in enumerate(others):
                if obs[p + 88 + slot] > 0.5:
                    positions[peer] = (r, c)
            if obs[p + 91] > 0.01 or obs[p + 93] > 0.5:
                cells.append((r, c, p))
            if obs[p + 95] > 0.01:
                active.append((r, c))
    return positions, cells, active


def _dashboard(obs, agent_id):
    order = [agent_id] + [i for i in range(3) if i != agent_id]
    alive = {}
    health = {}
    for slot, peer in enumerate(order):
        p = SPATIAL + 18 * slot
        health[peer] = 10.0 * obs[p]
        alive[peer] = obs[p + 1] > 0.5
    return alive, health


def _facing(obs):
    for k in range(4):
        if obs[DIRECTION + k] > 0.5:
            return k + 1
    return 0


def _toward(source, target):
    delta = (target[0] - source[0], target[1] - source[1])
    return {(-1, 0): 3, (1, 0): 4, (0, -1): 1, (0, 1): 2}.get(delta)


def _choose(obs, mask, positions, cells, active, alive, health, blocked):
    best = None
    for r, c, p in cells:
        if any(abs(r - ar) + abs(c - ac) <= 2 for ar, ac in active):
            continue
        mob = _mob(obs, p)
        block = _block(obs, p)
        if obs[p + 93] > 0.5:
            if not 8 <= mob < 16:
                continue
            kind, required, hard, action = 2, 2, obs[p + 94] > 0.5, 5
        elif obs[p + 91] > 0.01:
            if mob >= 0 or block in PASSABLE or block >= 38:
                continue
            required = int(round(obs[p + 91] * 3))
            if required not in (2, 3):
                continue
            hard = obs[p + 92] < 0.5
            if block == 37:
                action = next((a for a in BUILD_ACTIONS if a < len(mask) and mask[a]), None)
                if action is None:
                    continue
                kind = 0
            else:
                kind, action = 1, 5
        else:
            continue
        group = tuple(i for i in range(3)
                      if i in positions and alive[i] and health[i] >= 4.0
                      and abs(positions[i][0] - r) + abs(positions[i][1] - c) == 1)
        if len(group) < required or action >= len(mask) or not mask[action]:
            continue
        anchor = positions[group[0]]
        relative = (r - anchor[0], c - anchor[1])
        key_parts = (kind, block, mob, required, int(hard), action, len(group)) + group + relative
        key = ':'.join(map(str, key_parts))
        if key in blocked:
            continue
        priority = 0 if kind == 0 else (1 if kind == 1 and hard else 2 if kind == 1 else 3)
        rank = (priority, -len(group), group, relative, block, mob, action)
        if best is None or rank < best[0]:
            best = (rank, key, group, (r, c), action)
    return best


def _act(local, memory):
    proposal = int(local['proposal'])
    obs = local['observation']
    mask = local['legal_mask']
    if len(obs) < DIRECTION + 4 or len(mask) < 6:
        return {'action': proposal, 'memory': memory}
    agent_id = int(memory['id'])
    step = int(local['step'])
    memory['cool'] = [entry for entry in memory.get('cool', []) if entry[1] > step]

    def finish(action):
        if action is None or action < 0 or action >= len(mask) or not mask[action]:
            action = proposal
        return {'action': action, 'memory': memory}

    if not mask[5] or proposal in (6, 17, 18, 19):
        memory['focus'], memory['phase'] = None, 0
        return finish(proposal)
    alive, health = _dashboard(obs, agent_id)
    if health[agent_id] < 4.0 or min(obs[INTRINSICS:INTRINSICS + 3]) < 0.11:
        memory['focus'], memory['phase'] = None, 0
        return finish(proposal)
    positions, cells, active = _scan(obs, agent_id)
    blocked = {entry[0] for entry in memory['cool']}
    choice = _choose(obs, mask, positions, cells, active, alive, health, blocked)
    if choice is None or agent_id not in choice[2]:
        memory['focus'], memory['phase'] = None, 0
        return finish(proposal)
    _, key, group, target, interaction = choice
    direction = _toward(positions[agent_id], target)
    if direction is None:
        memory['focus'], memory['phase'] = None, 0
        return finish(proposal)
    facing = _facing(obs)
    if memory.get('focus') != key:
        memory['focus'], memory['phase'] = key, 1
        return finish(direction if facing != direction else 0)
    if facing != direction:
        return finish(direction)
    phase = int(memory.get('phase', 1))
    if phase <= 2:
        memory['phase'] = phase + 1
        return finish(interaction)
    memory['cool'] = (memory['cool'] + [[key, step + 18]])[-12:]
    memory['focus'], memory['phase'] = None, 0
    return finish(proposal)


def act(local, memory):
    if not isinstance(memory, dict):
        memory = {}
    try:
        return _act(local, memory)
    except Exception:
        return {'action': int(local['proposal']), 'memory': memory}

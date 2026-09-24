H, W, C = 9, 11, 97
SPATIAL = H * W * C
DIRECTION = SPATIAL + 54 + 24 + 16 + 6 + 8
MOVES = ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0))
MINEABLE = (4, 5, 8, 9, 10, 21, 22, 28, 29)


def initialize(agent_id, schema):
    return {'id': int(agent_id), 'plan': None, 'last': None,
            'avoid': None, 'attempts': 0}


def _finish(local, memory, action):
    mask = local['legal_mask']
    if action is None or not 0 <= action < len(mask) or not mask[action]:
        action = int(local['proposal'])
    return {'action': int(action), 'memory': memory}


def _facing(obs):
    for index in range(4):
        if obs[DIRECTION + index] > 0.5:
            return index + 1
    return 0


def _status(obs, agent_id):
    order = [agent_id] + [peer for peer in range(3) if peer != agent_id]
    alive, health = {}, {}
    for slot, peer in enumerate(order):
        base = SPATIAL + 18 * slot
        alive[peer] = obs[base + 1] > 0.5
        health[peer] = obs[base] * 10.0
    return alive, health


def _positions(obs, agent_id):
    positions = {agent_id: (4, 5)}
    for row in range(H):
        for col in range(W):
            base = (row * W + col) * C
            if obs[base + 96] < 0.5:
                continue
            for peer in range(3):
                if peer == agent_id:
                    continue
                channel = 87 + (peer + 1 if peer < agent_id else peer)
                if obs[base + channel] > 0.5:
                    positions[peer] = (row, col)
    return positions


def _active_handover(obs):
    for tile in range(H * W):
        if obs[tile * C + 95] > 0.001:
            return True
    return False


def _kind(obs, row, col):
    if not (0 <= row < H and 0 <= col < W):
        return -1
    base = (row * W + col) * C
    if obs[base + 96] < 0.5:
        return -1
    for block in MINEABLE:
        if obs[base + block] > 0.5:
            return block
    if obs[base + 37] > 0.5:
        return 37
    if obs[base + 93] > 0.5:
        for mob_type in range(8):
            if obs[base + 55 + mob_type] > 0.5:
                return 100 + mob_type
    return -1


def _task(obs, mask, positions, alive, health, agent_id, row, col):
    if abs(row - 4) + abs(col - 5) != 1:
        return None
    kind = _kind(obs, row, col)
    if kind < 0:
        return None
    base = (row * W + col) * C
    group = tuple(peer for peer in range(3)
                  if alive[peer] and health[peer] >= 5.0
                  and peer in positions
                  and abs(positions[peer][0] - row)
                  + abs(positions[peer][1] - col) == 1)
    if agent_id not in group:
        return None

    if kind < 100:
        value = obs[base + 91]
        if value < 0.49:
            return None
        required = int(value * 3.0 + 0.5)
        if required not in (2, 3):
            return None
        hard = obs[base + 92] < 0.5
        if kind == 37:
            builds = [action for action in (51, 52, 53)
                      if action < len(mask) and mask[action]]
            if not builds:
                return None
            action = builds[0]
            priority = 4 if hard else 2
        else:
            action = 5
            priority = 3 if hard else 1
    else:
        required = 2
        action = 5
        priority = 2 if obs[base + 94] > 0.5 else 0

    if len(group) < required or action >= len(mask) or not mask[action]:
        return None
    return action, kind, required, group, priority


def _select(obs, mask, positions, alive, health, agent_id, memory, step):
    best = None
    avoid = memory.get('avoid')
    for direction in range(1, 5):
        row = 4 + MOVES[direction][0]
        col = 5 + MOVES[direction][1]
        task = _task(obs, mask, positions, alive, health,
                     agent_id, row, col)
        if task is None:
            continue
        action, kind, required, group, priority = task
        if (isinstance(avoid, list) and len(avoid) == 4
                and step < avoid[0]
                and [row, col, kind] == avoid[1:]):
            continue
        leader = group[0]
        anchor = positions[leader]
        key = (-priority, -required, -len(group), leader,
               row - anchor[0], col - anchor[1], kind, action)
        plan = [step + 1, row, col, direction, action, kind,
                required, sum(1 << peer for peer in group)]
        if best is None or key < best[0]:
            best = (key, plan)
    return None if best is None else best[1]


def _act(local, memory):
    obs = local['observation']
    mask = local['legal_mask']
    step = int(local['step'])
    proposal = int(local['proposal'])
    if len(obs) <= DIRECTION + 3 or len(mask) < 54 or not mask[5]:
        memory['plan'] = None
        return _finish(local, memory, proposal)

    agent_id = int(memory['id'])
    last = memory.get('last')
    memory['last'] = None
    if (isinstance(last, list) and len(last) == 4
            and last[0] == step - 1
            and _kind(obs, last[1], last[2]) == last[3]):
        memory['avoid'] = [step + 12, last[1], last[2], last[3]]

    if _active_handover(obs):
        memory['plan'] = None
        return _finish(local, memory, proposal)

    alive, health = _status(obs, agent_id)
    positions = _positions(obs, agent_id)
    plan = memory.get('plan')
    memory['plan'] = None
    if isinstance(plan, list) and len(plan) == 8:
        if plan[0] == step:
            _, row, col, direction, action, kind, required, members = plan
            task = _task(obs, mask, positions, alive, health,
                         agent_id, row, col)
            if (task is not None and task[0] == action
                    and task[1] == kind and task[2] == required
                    and _facing(obs) == direction
                    and sum(1 for peer in task[3]
                            if members & (1 << peer)) >= required):
                memory['attempts'] = int(memory.get('attempts', 0)) + 1
                memory['last'] = [step, row, col, kind]
                return _finish(local, memory, action)
        return _finish(local, memory, proposal)

    if int(memory.get('attempts', 0)) >= 8:
        return _finish(local, memory, proposal)
    choice = _select(obs, mask, positions, alive, health,
                     agent_id, memory, step)
    if choice is None:
        return _finish(local, memory, proposal)
    memory['plan'] = choice
    direction = choice[3]
    preparation = direction if _facing(obs) != direction else 0
    return _finish(local, memory, preparation)


def act(local, memory):
    if not isinstance(memory, dict):
        return {'action': int(local['proposal']), 'memory': {}}
    try:
        return _act(local, memory)
    except Exception:
        return {'action': int(local['proposal']), 'memory': memory}

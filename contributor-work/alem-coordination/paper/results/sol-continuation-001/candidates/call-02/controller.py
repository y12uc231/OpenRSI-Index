H, W, C = 9, 11, 97
SPATIAL = H * W * C
INTRINSICS = SPATIAL + 54 + 24 + 16 + 6
DIRECTION = INTRINSICS + 8
MOVES = ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0))
MINEABLE = (4, 5, 8, 9, 10, 21, 22, 28, 29)
URGENT = (6, 17, 18, 19, 24, 26, 28, 29, 30, 31, 32, 33, 34, 38, 39, 40)


def initialize(agent_id, schema):
    return {
        'id': int(agent_id),
        'comm': [int(x) for x in schema.get('native_comm_action_ids', ())],
        'plan': None,
        'cool': 0,
        'sent': -100,
    }


def _finish(local, memory, action):
    mask = local['legal_mask']
    proposal = int(local['proposal'])
    if action is None or action < 0 or action >= len(mask) or not mask[action]:
        action = proposal
    return {'action': int(action), 'memory': memory}


def _facing(obs):
    for k in range(4):
        if obs[DIRECTION + k] > 0.5:
            return k + 1
    return 0


def _toward(source, target):
    delta = (target[0] - source[0], target[1] - source[1])
    for direction in range(1, 5):
        if delta == MOVES[direction]:
            return direction
    return None


def _status(obs, agent_id):
    order = [agent_id] + [i for i in range(3) if i != agent_id]
    alive, health = {}, {}
    for slot, peer in enumerate(order):
        base = SPATIAL + 18 * slot
        alive[peer] = obs[base + 1] > 0.5
        health[peer] = 10.0 * obs[base]
    return alive, health


def _view(obs, agent_id):
    peers = [i for i in range(3) if i != agent_id]
    positions = {agent_id: (4, 5)}
    active_handover = False
    for row in range(H):
        for col in range(W):
            base = (row * W + col) * C
            if obs[base + 96] < 0.5:
                continue
            if obs[base + 95] > 0.001:
                active_handover = True
            for slot, peer in enumerate(peers):
                if obs[base + 88 + slot] > 0.5:
                    positions[peer] = (row, col)
    return positions, active_handover


def _task(obs, mask, positions, alive, health, row, col):
    if not (0 <= row < H and 0 <= col < W):
        return None
    if abs(row - 4) + abs(col - 5) != 1:
        return None
    base = (row * W + col) * C
    if obs[base + 96] < 0.5 or obs[base + 95] > 0.001:
        return None
    value = obs[base + 91]
    if value < 0.49:
        return None
    required = int(round(value * 3.0))
    if required not in (2, 3):
        return None

    block = -1
    for kind in MINEABLE:
        if obs[base + kind] > 0.5:
            block = kind
            break
    if block in MINEABLE:
        action = 5
    elif obs[base + 37] > 0.5:
        block = 37
        builds = [a for a in (51, 52, 53) if a < len(mask) and mask[a]]
        if len(builds) != 1:
            return None
        action = builds[0]
    else:
        return None
    if action >= len(mask) or not mask[action]:
        return None

    group = tuple(sorted(
        peer for peer, pos in positions.items()
        if alive.get(peer, False) and health.get(peer, 0.0) >= 4.0
        and abs(pos[0] - row) + abs(pos[1] - col) == 1
    ))
    if len(group) < required:
        return None
    return action, block, group


def _incoming(obs, mask, memory, positions, alive, health, step):
    agent_id = int(memory['id'])
    order = [agent_id] + [i for i in range(3) if i != agent_id]
    choices = []
    for slot, sender in enumerate(order):
        if sender not in positions or not alive[sender]:
            continue
        if sender == agent_id and memory.get('sent') != step - 1:
            continue
        dashboard = SPATIAL + 18 * slot
        for channel in range(4):
            if obs[dashboard + 14 + channel] <= 0.5:
                continue
            offset = MOVES[channel + 1]
            row = positions[sender][0] + offset[0]
            col = positions[sender][1] + offset[1]
            task = _task(obs, mask, positions, alive, health, row, col)
            if task is None or sender not in task[2]:
                continue
            direction = _toward((4, 5), (row, col))
            if direction is not None:
                choices.append((sender, channel, direction, task[0], task[1]))
    return min(choices) if choices else None


def _act(local, memory):
    proposal = int(local['proposal'])
    obs = local['observation']
    mask = local['legal_mask']
    step = int(local['step'])
    if len(obs) < DIRECTION + 4 or len(mask) < 54:
        return _finish(local, memory, proposal)

    agent_id = int(memory['id'])
    alive, health = _status(obs, agent_id)
    if (not mask[5] or proposal in URGENT or health[agent_id] < 4.0
            or min(obs[INTRINSICS:INTRINSICS + 3]) < 0.2):
        memory['plan'] = None
        return _finish(local, memory, proposal)

    positions, active_handover = _view(obs, agent_id)
    if active_handover:
        memory['plan'] = None
        return _finish(local, memory, proposal)

    plan = memory.get('plan')
    if isinstance(plan, list) and len(plan) == 4:
        memory['plan'] = None
        if int(plan[0]) == step:
            direction = int(plan[1])
            offset = MOVES[direction]
            row, col = 4 + offset[0], 5 + offset[1]
            task = _task(obs, mask, positions, alive, health, row, col)
            if (task is not None and task[0] == int(plan[2])
                    and task[1] == int(plan[3]) and _facing(obs) == direction):
                return _finish(local, memory, task[0])

    invite = _incoming(obs, mask, memory, positions, alive, health, step)
    if invite is not None:
        direction, action, block = invite[2], invite[3], invite[4]
        memory['plan'] = [step + 1, direction, action, block]
        memory['cool'] = max(int(memory.get('cool', 0)), step + 8)
        preparation = direction if _facing(obs) != direction else 0
        return _finish(local, memory, preparation)

    if step >= int(memory.get('cool', 0)) and proposal in (5, 51, 52, 53):
        direction = _facing(obs)
        if direction:
            offset = MOVES[direction]
            task = _task(obs, mask, positions, alive, health,
                         4 + offset[0], 5 + offset[1])
            if task is not None and task[0] == proposal:
                comm = memory.get('comm', ())
                if len(comm) == 4:
                    signal = int(comm[direction - 1])
                    if 0 <= signal < len(mask) and mask[signal]:
                        memory['sent'] = step
                        memory['cool'] = step + 8
                        return _finish(local, memory, signal)

    return _finish(local, memory, proposal)


def act(local, memory):
    if not isinstance(memory, dict):
        memory = {}
    try:
        return _act(local, memory)
    except Exception:
        return {'action': int(local['proposal']), 'memory': memory}

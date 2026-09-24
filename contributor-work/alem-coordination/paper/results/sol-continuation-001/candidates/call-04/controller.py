H, W, C = 9, 11, 97
SPATIAL = H * W * C
INVENTORY = SPATIAL + 54 + 24
INTRINSICS = INVENTORY + 16 + 6
FACING = INTRINSICS + 8
MOVES = ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0))
RESOURCES = (4, 5, 8, 9, 10, 21, 22, 28, 29)
HOSTILES = tuple(range(47, 55)) + tuple(range(63, 87))


def initialize(agent_id, schema):
    return {
        'id': int(agent_id),
        'comm': [int(a) for a in schema.get('native_comm_action_ids', [])],
        'plan': None,
        'cooldown': None,
        'starts': 0,
        'used': 0,
        'revive_attempted': [],
    }


def _finish(local, memory, action):
    mask = local['legal_mask']
    try:
        action = int(action)
    except (TypeError, ValueError):
        action = -1
    if action < 0 or action >= len(mask) or not mask[action]:
        action = int(local['proposal'])
    if action < 0 or action >= len(mask) or not mask[action]:
        action = next((i for i, legal in enumerate(mask) if legal), 0)
    return {'action': action, 'memory': memory}


def _facing(obs):
    for direction in range(1, 5):
        if obs[FACING + direction - 1] > 0.5:
            return direction
    return 0


def _direction(row, col):
    offset = (row - 4, col - 5)
    for direction in range(1, 5):
        if MOVES[direction] == offset:
            return direction
    return 0


def _dashboard(obs, agent_id):
    order = [agent_id] + [p for p in range(3) if p != agent_id]
    health, alive, messages = {}, {}, {}
    for slot, peer in enumerate(order):
        base = SPATIAL + 18 * slot
        health[peer] = obs[base] * 10.0
        alive[peer] = obs[base + 1] > 0.5
        messages[peer] = obs[base + 14:base + 18]
    return health, alive, messages


def _positions(obs, agent_id):
    positions = {agent_id: (4, 5)}
    for row in range(H):
        for col in range(W):
            base = (row * W + col) * C
            if obs[base + 96] <= 0.5:
                continue
            for peer in range(3):
                if peer == agent_id:
                    continue
                channel = 87 + (peer + 1 if peer < agent_id else peer)
                if obs[base + channel] > 0.5:
                    positions[peer] = (row, col)
    return positions


def _block(obs, row, col):
    if not (0 <= row < H and 0 <= col < W):
        return -1
    base = (row * W + col) * C
    if obs[base + 96] <= 0.5:
        return -1
    for kind in RESOURCES:
        if obs[base + kind] > 0.5:
            return kind
    if obs[base + 37] > 0.5:
        return 37
    return -1


def _danger(obs, positions, group):
    for row in range(H):
        for col in range(W):
            base = (row * W + col) * C
            if obs[base + 96] <= 0.5:
                continue
            if not any(obs[base + channel] > 0.5 for channel in HOSTILES):
                continue
            for peer in group:
                pr, pc = positions[peer]
                if abs(pr - row) + abs(pc - col) <= 2:
                    return True
    return False


def _candidate(obs, mask, positions, health, alive, agent_id):
    if min(obs[INTRINSICS:INTRINSICS + 3]) < 0.2:
        return None
    best = None
    for direction in range(1, 5):
        row = 4 + MOVES[direction][0]
        col = 5 + MOVES[direction][1]
        base = (row * W + col) * C
        if obs[base + 96] <= 0.5 or obs[base + 91] < 0.49:
            continue
        if obs[base + 92] > 0.5:
            continue
        required = int(obs[base + 91] * 3.0 + 0.5)
        if required not in (2, 3):
            continue
        kind = _block(obs, row, col)
        if kind == 37:
            action = next((a for a in (51, 52, 53)
                           if a < len(mask) and mask[a]), None)
            priority = 2
        elif kind in RESOURCES:
            action = 5
            priority = 1
        else:
            continue
        if action is None:
            continue
        group = [p for p in range(3)
                 if alive[p] and health[p] >= 6.0 and p in positions
                 and abs(positions[p][0] - row)
                 + abs(positions[p][1] - col) == 1]
        if agent_id not in group or len(group) < required:
            continue
        if _danger(obs, positions, group):
            continue
        leader = group[0]
        relative_row = row - positions[leader][0]
        relative_col = col - positions[leader][1]
        rank = (-priority, -required, -len(group), leader,
                relative_row, relative_col, kind, action)
        signature = [row, col, kind, action, required, leader,
                     relative_row, relative_col] + group
        channel = ((relative_row + 3) * 11 + (relative_col + 3) * 17
                   + kind * 7 + action * 3 + required) % 4
        candidate = {'signature': signature, 'direction': direction,
                     'action': action, 'channel': channel, 'group': group}
        if best is None or rank < best[0]:
            best = (rank, candidate)
    return None if best is None else best[1]


def _revive(positions, health, alive, agent_id, facing, memory):
    attempted = memory.get('revive_attempted')
    if not isinstance(attempted, list):
        attempted = []
    attempted[:] = [p for p in attempted if p in alive and not alive[p]]
    memory['revive_attempted'] = attempted
    if health[agent_id] < 3.0:
        return None
    for peer in range(3):
        if peer == agent_id or alive[peer] or peer in attempted:
            continue
        if peer not in positions:
            continue
        row, col = positions[peer]
        direction = _direction(row, col)
        if direction == 0:
            continue
        if facing == direction:
            attempted.append(peer)
            return 5
        return direction
    return None


def _best_without_do(local):
    mask = local['legal_mask']
    logits = local['frozen_logits']
    best_action = 0
    best_logit = -1e300
    for action, legal in enumerate(mask):
        if not legal or action == 5 or action >= len(logits):
            continue
        if logits[action] > best_logit:
            best_logit = logits[action]
            best_action = action
    return best_action


def _sync(local, memory, positions, health, alive, messages, facing):
    comm = memory.get('comm', [])
    if len(comm) != 4 or memory.get('used', 0) >= 4:
        memory['plan'] = None
        return None
    obs = local['observation']
    step = int(local['step'])
    candidate = _candidate(obs, local['legal_mask'], positions,
                           health, alive, memory['id'])
    if candidate is None:
        memory['plan'] = None
        return None
    signature = candidate['signature']
    cooldown = memory.get('cooldown')
    if (isinstance(cooldown, list) and len(cooldown) == 2
            and step < cooldown[0] and cooldown[1] == signature):
        memory['plan'] = None
        return None
    plan = memory.get('plan')
    if not isinstance(plan, dict) or plan.get('signature') != signature:
        if memory.get('starts', 0) >= 5:
            memory['plan'] = None
            return None
        plan = {'signature': signature, 'start': step, 'sent': -100}
        memory['plan'] = plan
        memory['starts'] = memory.get('starts', 0) + 1
    if step - plan['start'] > 5:
        memory['cooldown'] = [step + 18, signature]
        memory['plan'] = None
        return None
    if facing != candidate['direction']:
        return candidate['direction']
    channel = candidate['channel']
    if plan['sent'] == step - 1:
        if all(messages[p][channel] > 0.5
               for p in candidate['group'] if p != memory['id']):
            memory['plan'] = None
            memory['cooldown'] = [step + 12, signature]
            memory['used'] = memory.get('used', 0) + 1
            return candidate['action']
    plan['sent'] = step
    return comm[channel]


def _act(local, memory):
    obs = local['observation']
    mask = local['legal_mask']
    proposal = int(local['proposal'])
    if len(obs) <= FACING + 3 or len(mask) <= 5 or not mask[5]:
        memory['plan'] = None
        return _finish(local, memory, proposal)
    agent_id = int(memory['id'])
    health, alive, messages = _dashboard(obs, agent_id)
    positions = _positions(obs, agent_id)
    facing = _facing(obs)
    rescue = _revive(positions, health, alive, agent_id, facing, memory)
    if rescue is not None:
        memory['plan'] = None
        return _finish(local, memory, rescue)
    if proposal == 5 and facing:
        faced = (4 + MOVES[facing][0], 5 + MOVES[facing][1])
        if any(alive[p] and positions.get(p) == faced
               for p in range(3) if p != agent_id):
            memory['plan'] = None
            return _finish(local, memory, _best_without_do(local))
    action = _sync(local, memory, positions, health, alive, messages, facing)
    return _finish(local, memory, proposal if action is None else action)


def act(local, memory):
    if not isinstance(memory, dict):
        return {'action': int(local['proposal']), 'memory': {}}
    try:
        return _act(local, memory)
    except Exception:
        return _finish(local, memory, local['proposal'])

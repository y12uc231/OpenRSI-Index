H, W, C = 9, 11, 97
SPATIAL = H * W * C
FACING = SPATIAL + 54 + 24 + 16 + 6 + 8
INVENTORY = SPATIAL + 54 + 24
DIRS = ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0))
GROUPS = ((0, 1), (0, 2), (1, 2), (0, 1, 2))
STATIC = (37, 5, 4, 8, 9, 10, 21, 22, 28, 29, 15, 16)
HOSTILE = tuple(range(47, 55)) + tuple(range(63, 79))
BUILD = (52, 51, 53)


def initialize(agent_id, schema):
    return {'id': int(agent_id), 'plan': None, 'recent': []}


def _reply(local, memory, action):
    mask = local['legal_mask']
    try:
        action = int(action)
    except (TypeError, ValueError):
        action = -1
    if action < 0 or action >= len(mask) or not mask[action]:
        try:
            action = int(local['proposal'])
        except (TypeError, ValueError):
            action = -1
    if action < 0 or action >= len(mask) or not mask[action]:
        action = next((i for i, legal in enumerate(mask) if legal), 0)
    return {'action': action, 'memory': memory}


def _facing(obs):
    for direction in range(1, 5):
        if obs[FACING + direction - 1] > 0.5:
            return direction
    return 0


def _state(obs, agent_id):
    order = [agent_id] + [p for p in range(3) if p != agent_id]
    health, alive = {}, {}
    for slot, peer in enumerate(order):
        base = SPATIAL + 18 * slot
        health[peer] = 10.0 * obs[base]
        alive[peer] = obs[base + 1] > 0.5
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
    return health, alive, positions


def _danger(obs, row, col):
    for r in range(max(0, row - 2), min(H, row + 3)):
        for c in range(max(0, col - 2), min(W, col + 3)):
            if abs(r - row) + abs(c - col) > 2:
                continue
            base = (r * W + c) * C
            if obs[base + 96] > 0.5:
                for channel in HOSTILE:
                    if obs[base + channel] > 0.5:
                        return True
    return False


def _target(obs, mask, base):
    value = obs[base + 91]
    if value > 0.49:
        required = int(3.0 * value + 0.5)
        if required in (2, 3):
            for kind in STATIC:
                if obs[base + kind] > 0.5:
                    if kind == 37:
                        choices = [a for a in BUILD if a < len(mask) and mask[a]]
                        if not choices:
                            return None
                        action = choices[0]
                    else:
                        action = 5
                    return (required, obs[base + 92] > 0.5, kind, action)
    if obs[base + 93] > 0.5:
        for kind in range(55, 63):
            if obs[base + kind] > 0.5:
                return (2, obs[base + 94] < 0.5, kind, 5)
    return None


def _cooling(memory, signature):
    return any(entry[0] == signature for entry in memory['recent'])


def _mark(memory, signature, step, duration):
    memory['recent'].append([signature, step + duration])
    memory['recent'] = memory['recent'][-32:]


def _eligible(group, health, alive, positions):
    return all(p in positions and alive[p] and health[p] >= 5.0 for p in group)


def _pick_sync(obs, mask, memory, step, health, alive, positions):
    phase = (step // 2) % len(GROUPS)
    group = GROUPS[phase]
    if memory['id'] not in group or not _eligible(group, health, alive, positions):
        return None
    best = None
    leader_row, leader_col = positions[group[0]]
    for row in range(H):
        for col in range(W):
            if any(abs(positions[p][0] - row) + abs(positions[p][1] - col) != 1 for p in group):
                continue
            base = (row * W + col) * C
            if obs[base + 96] <= 0.5:
                continue
            target = _target(obs, mask, base)
            if target is None or target[0] > len(group) or _danger(obs, row, col):
                continue
            relative = (row - leader_row, col - leader_col)
            signature = ['sync', phase, relative[0], relative[1], target[2], target[3]]
            if _cooling(memory, signature):
                continue
            rank = (0 if target[2] == 37 else 1, int(target[1]), -target[0],
                    target[2], relative[0], relative[1])
            candidate = (rank, row, col, list(target), signature, phase)
            if best is None or rank < best[0]:
                best = candidate
    return best


def _valid_sync(obs, mask, plan, health, alive, positions):
    group = GROUPS[plan['phase']]
    if not _eligible(group, health, alive, positions):
        return False
    row, col = plan['row'], plan['col']
    if any(abs(positions[p][0] - row) + abs(positions[p][1] - col) != 1 for p in group):
        return False
    base = (row * W + col) * C
    if obs[base + 96] <= 0.5 or _danger(obs, row, col):
        return False
    target = _target(obs, mask, base)
    return (target is not None and list(target) == plan['target']
            and mask[plan['action']] and _facing(obs) == plan['direction'])


def _quantity(obs, offset):
    value = 10.0 * obs[INVENTORY + offset]
    return int(value * value + 0.5)


def _can_pay(obs, action):
    wood = _quantity(obs, 0)
    stone = _quantity(obs, 1)
    coal = _quantity(obs, 2)
    iron = _quantity(obs, 3)
    if action == 51:
        return wood >= 10 and stone >= 5
    if action == 52:
        return stone >= 10 and iron >= 3 and coal >= 2
    if action == 53:
        return iron >= 3 and coal >= 2
    return False


def _single_build(mask):
    choices = [a for a in BUILD if a < len(mask) and mask[a]]
    return choices[0] if len(choices) == 1 else None


def _helper(row, col, agent_id, health, alive, positions):
    return any(p != agent_id and p in positions and alive[p] and health[p] >= 5.0
               and abs(positions[p][0] - row) + abs(positions[p][1] - col) == 1
               for p in range(3))


def _valid_site(obs, mask, plan, health, alive, positions, agent_id):
    row, col, action = plan['row'], plan['col'], plan['action']
    base = (row * W + col) * C
    if obs[base + 96] <= 0.5 or _danger(obs, row, col):
        return False
    if _facing(obs) != plan['direction'] or action >= len(mask) or not mask[action]:
        return False
    if plan['mode'] == 'complete':
        return (obs[base + 41] > 0.5 and obs[base + 95] > 0.0
                and _single_build(mask) == action)
    return (obs[base + 37] > 0.5 and obs[base + 91] < -0.05
            and _can_pay(obs, action)
            and _helper(row, col, agent_id, health, alive, positions))


def _pick_site(obs, mask, memory, step, health, alive, positions):
    facing = _facing(obs)
    best = None
    for direction in range(1, 5):
        dr, dc = DIRS[direction]
        row, col = 4 + dr, 5 + dc
        base = (row * W + col) * C
        if obs[base + 96] <= 0.5 or _danger(obs, row, col):
            continue
        mode, action = None, None
        if obs[base + 41] > 0.5 and obs[base + 95] > 0.0:
            if facing == direction or obs[base + 95] >= 0.2:
                action = _single_build(mask)
                if action is not None:
                    mode = 'complete'
        elif (obs[base + 37] > 0.5 and obs[base + 91] < -0.05
              and _helper(row, col, memory['id'], health, alive, positions)):
            for candidate in BUILD:
                if candidate < len(mask) and mask[candidate] and _can_pay(obs, candidate):
                    action, mode = candidate, 'setup'
                    break
        if action is None:
            continue
        signature = ['site', mode, direction, action]
        if _cooling(memory, signature):
            continue
        rank = (0 if mode == 'complete' else 1, BUILD.index(action), direction)
        candidate = (rank, mode, action, direction, row, col, signature)
        if best is None or rank < best[0]:
            best = candidate
    return best


def _act(local, memory):
    obs = local['observation']
    mask = local['legal_mask']
    proposal = local['proposal']
    if len(obs) < FACING + 4 or len(mask) <= 53 or not mask[5]:
        memory['plan'] = None
        return _reply(local, memory, proposal)
    step = int(local['step'])
    memory['recent'] = [entry for entry in memory.get('recent', [])
                        if isinstance(entry, list) and len(entry) == 2 and entry[1] > step][-32:]
    health, alive, positions = _state(obs, memory['id'])
    plan = memory.get('plan')
    memory['plan'] = None
    if isinstance(plan, dict) and step == plan['step'] + 1:
        if plan['mode'] == 'sync' and _valid_sync(obs, mask, plan, health, alive, positions):
            return _reply(local, memory, plan['action'])
        if plan['mode'] in ('complete', 'setup') and _valid_site(
                obs, mask, plan, health, alive, positions, memory['id']):
            return _reply(local, memory, plan['action'])
    site = _pick_site(obs, mask, memory, step, health, alive, positions)
    if site is not None:
        _, mode, action, direction, row, col, signature = site
        _mark(memory, signature, step, 10)
        if _facing(obs) == direction:
            return _reply(local, memory, action)
        memory['plan'] = {'mode': mode, 'step': step, 'row': row, 'col': col,
                          'direction': direction, 'action': action}
        return _reply(local, memory, direction)
    if step % 2 == 0:
        chosen = _pick_sync(obs, mask, memory, step, health, alive, positions)
        if chosen is not None:
            _, row, col, target, signature, phase = chosen
            direction = next((d for d in range(1, 5)
                              if (row - 4, col - 5) == DIRS[d]), 0)
            if direction and mask[direction]:
                _mark(memory, signature, step, 12)
                memory['plan'] = {'mode': 'sync', 'step': step, 'row': row,
                                  'col': col, 'direction': direction,
                                  'action': target[3], 'target': target, 'phase': phase}
                return _reply(local, memory, direction)
    return _reply(local, memory, proposal)


def act(local, memory):
    if not isinstance(memory, dict):
        obs = local.get('observation', [])
        agent_id = max(range(3), key=lambda i: obs[-3 + i]) if len(obs) >= 3 else 0
        memory = initialize(agent_id, {})
    try:
        return _act(local, memory)
    except Exception:
        return _reply(local, memory, local['proposal'])

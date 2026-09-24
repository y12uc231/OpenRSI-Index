H, W, C = 9, 11, 97
SPATIAL = H * W * C
FACING = SPATIAL + 54 + 24 + 16 + 6 + 8
TARGETS = (4, 5, 8, 9, 10, 21, 22, 28, 29)
HOSTILES = tuple(range(47, 55)) + tuple(range(63, 79))
DIRECTIONS = ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0))


def initialize(agent_id, schema):
    return {'id': int(agent_id), 'pending': None, 'last': None, 'starts': 0}


def _reply(local, memory, action):
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
        if DIRECTIONS[direction] == offset:
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


def _kind(obs, base):
    for kind in TARGETS:
        if obs[base + kind] > 0.5:
            return kind
    return -1


def _danger(obs, row, col):
    for r in range(max(0, row - 2), min(H, row + 3)):
        for c in range(max(0, col - 2), min(W, col + 3)):
            if abs(r - row) + abs(c - col) > 2:
                continue
            base = (r * W + c) * C
            if obs[base + 96] > 0.5:
                for channel in HOSTILES:
                    if obs[base + channel] > 0.5:
                        return True
    return False


def _choose(obs, health, alive, positions):
    best = None
    for row in range(1, 8):
        for col in range(2, 9):
            if abs(row - 4) + abs(col - 5) > 3:
                continue
            base = (row * W + col) * C
            if obs[base + 96] <= 0.5 or obs[base + 91] <= 0.49:
                continue
            if obs[base + 92] > 0.5:
                continue
            required = int(3.0 * obs[base + 91] + 0.5)
            if required not in (2, 3):
                continue
            kind = _kind(obs, base)
            if kind < 0:
                continue
            group = [p for p in range(3)
                     if p in positions and alive[p] and health[p] >= 5.0
                     and abs(positions[p][0] - row)
                     + abs(positions[p][1] - col) == 1]
            if len(group) < required or _danger(obs, row, col):
                continue
            leader = group[0]
            leader_row, leader_col = positions[leader]
            relative_row = row - leader_row
            relative_col = col - leader_col
            rank = (leader, -required, -len(group), relative_row,
                    relative_col, kind)
            signature = [leader, relative_row, relative_col,
                         kind, required] + group
            candidate = {'row': row, 'col': col, 'kind': kind,
                         'required': required, 'group': group,
                         'signature': signature}
            if best is None or rank < best[0]:
                best = (rank, candidate)
    return None if best is None else best[1]


def _pending_valid(obs, mask, pending, health, alive, positions):
    if not mask[5]:
        return False
    row, col = pending['row'], pending['col']
    if not (0 <= row < H and 0 <= col < W):
        return False
    base = (row * W + col) * C
    if obs[base + 96] <= 0.5 or _kind(obs, base) != pending['kind']:
        return False
    if (int(3.0 * obs[base + 91] + 0.5) != pending['required']
            or obs[base + 92] > 0.5):
        return False
    if _facing(obs) != pending['direction'] or _danger(obs, row, col):
        return False
    for peer in pending['group']:
        if (peer not in positions or not alive[peer] or health[peer] < 5.0
                or abs(positions[peer][0] - row)
                + abs(positions[peer][1] - col) != 1):
            return False
    return True


def _act(local, memory):
    obs = local['observation']
    mask = local['legal_mask']
    proposal = local['proposal']
    if len(obs) < FACING + 4 or len(mask) <= 5 or not mask[5]:
        memory['pending'] = None
        return _reply(local, memory, proposal)
    agent_id = memory['id']
    step = int(local['step'])
    health, alive, positions = _state(obs, agent_id)
    pending = memory.get('pending')
    if isinstance(pending, dict):
        memory['pending'] = None
        if step == pending['step'] + 1:
            memory['last'] = [pending['signature'], step + 10]
            if _pending_valid(obs, mask, pending, health, alive, positions):
                return _reply(local, memory, 5)
    if step % 2 == 0 and memory.get('starts', 0) < 8:
        candidate = _choose(obs, health, alive, positions)
        if candidate is not None and agent_id in candidate['group']:
            last = memory.get('last')
            cooling = (isinstance(last, list) and len(last) == 2
                       and last[0] == candidate['signature'] and step < last[1])
            direction = _direction(candidate['row'], candidate['col'])
            if direction and mask[direction] and not cooling:
                memory['pending'] = {
                    'step': step, 'row': candidate['row'],
                    'col': candidate['col'], 'kind': candidate['kind'],
                    'required': candidate['required'],
                    'group': candidate['group'],
                    'signature': candidate['signature'],
                    'direction': direction,
                }
                memory['starts'] = memory.get('starts', 0) + 1
                return _reply(local, memory, direction)
    return _reply(local, memory, proposal)


def act(local, memory):
    if not isinstance(memory, dict):
        memory = {}
    try:
        return _act(local, memory)
    except Exception:
        return _reply(local, memory, local['proposal'])

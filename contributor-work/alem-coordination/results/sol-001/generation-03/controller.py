from collections import deque
from itertools import combinations, permutations

H, W, C = 9, 11, 97
DASH = H * W * C
INV = DASH + 54 + 24
INTR = INV + 16 + 6
DIRECTION = INTR + 8
MOVES = ((3, -1, 0), (4, 1, 0), (1, 0, -1), (2, 0, 1))
PASSABLE = {2, 6, 7, 13, 26, 27}
ORE_TOOL = {4: 1, 8: 1, 9: 2, 10: 3, 21: 4, 22: 4}
BUILD_ACTIONS = (53, 52, 51)


def initialize(agent_id, schema):
    return {
        'id': int(agent_id),
        'comm': [int(a) for a in schema.get('native_comm_action_ids', [])],
        'focus': None,
        'age': 0,
        'cool': [],
        'last_start': None,
        'own_pending': None,
    }


def _inside(r, c):
    return 0 <= r < H and 0 <= c < W


def _base(r, c):
    return (r * W + c) * C


def _block(obs, r, c):
    if not _inside(r, c):
        return -1
    p = _base(r, c)
    if obs[p + 96] < 0.5:
        return -1
    for b in range(42):
        if obs[p + b] > 0.5:
            return b
    return -1


def _mob(obs, r, c):
    if not _inside(r, c):
        return -1
    p = _base(r, c)
    for k in range(40):
        if obs[p + 47 + k] > 0.5:
            return k
    return -1


def _signature(obs, r, c):
    p = _base(r, c)
    b = _block(obs, r, c)
    if b == 41:
        b = 37
    parts = [str(b), str(round(obs[p + 91] * 30)), str(_mob(obs, r, c))]
    for rr in range(r - 1, r + 2):
        for cc in range(c - 1, c + 2):
            x = _block(obs, rr, cc)
            parts.append(str(37 if x == 41 else x))
    return ':'.join(parts)


def _scan(obs, agent_id):
    others = [i for i in range(3) if i != agent_id]
    positions = {agent_id: (4, 5)}
    targets = []
    for r in range(H):
        for c in range(W):
            p = _base(r, c)
            if obs[p + 96] < 0.5:
                continue
            for k, peer in enumerate(others):
                if obs[p + 88 + k] > 0.5:
                    positions[peer] = (r, c)
            coord = obs[p + 91]
            active = obs[p + 95]
            mob_coord = obs[p + 93]
            if abs(coord) > 0.001 or active > 0.001 or mob_coord > 0.5:
                targets.append((r, c, _block(obs, r, c), coord,
                                obs[p + 92], mob_coord, obs[p + 94], active))
    return positions, targets


def _dashboard(obs, agent_id):
    order = [agent_id] + [i for i in range(3) if i != agent_id]
    data = {}
    for slot, peer in enumerate(order):
        p = DASH + 18 * slot
        data[peer] = {
            'health': obs[p] * 10.0,
            'alive': obs[p + 1] > 0.5,
            'comm': [obs[p + 14 + k] > 0.5 for k in range(4)],
        }
    return data


def _facing(obs):
    for k in range(4):
        if obs[DIRECTION + k] > 0.5:
            return k + 1
    return 0


def _toward(a, b):
    for action, dr, dc in MOVES:
        if (a[0] + dr, a[1] + dc) == b:
            return action
    return None


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _clear(obs, cell, positions, origin):
    if cell == positions[origin]:
        return True
    if any(cell == place for peer, place in positions.items() if peer != origin):
        return False
    return _block(obs, *cell) in PASSABLE and _mob(obs, *cell) < 0


def _path(obs, destination, positions, origin, limit=4):
    start = positions[origin]
    queue = deque([(start, ())])
    seen = {start}
    while queue:
        cell, path = queue.popleft()
        if cell == destination:
            return path
        if len(path) >= limit:
            continue
        for action, dr, dc in MOVES:
            nxt = (cell[0] + dr, cell[1] + dc)
            if nxt not in seen and _clear(obs, nxt, positions, origin):
                seen.add(nxt)
                queue.append((nxt, path + (action,)))
    return None


def _assignment(obs, positions, nearby, target, required):
    slots = []
    for _, dr, dc in MOVES:
        cell = (target[0] + dr, target[1] + dc)
        if _block(obs, *cell) in PASSABLE and _mob(obs, *cell) < 0:
            slots.append(cell)
    if len(slots) < required:
        return None
    best = None
    for group in combinations(nearby, required):
        for selected in permutations(slots, required):
            costs = []
            for peer, cell in zip(group, selected):
                route = _path(obs, cell, positions, peer)
                if route is None:
                    break
                cost = len(route)
                if cost and _distance(positions[peer], target) == 1:
                    cost += 3
                costs.append(cost)
            else:
                key = (sum(costs), max(costs), group, selected)
                if best is None or key < best[0]:
                    best = (key, group, dict(zip(group, selected)))
    if best is None:
        return None
    return best[1], best[2], best[0][0], best[0][1]


def _channel(tile, block, required, group, positions, count):
    anchor = positions[group[0]]
    return (7 * (tile[0] - anchor[0]) + 11 * (tile[1] - anchor[1])
            + 3 * block + required) % count


def _best_sync(obs, positions, stats, targets, agent_id, memory, tool):
    best = None
    blocked = {entry[0] for entry in memory['cool']}
    for target in targets:
        r, c, block, coord, soft, mob_coord, mob_hard, active = target
        if active > 0.001:
            continue
        if coord > 0.001:
            required = round(coord * 3)
            hard = soft < 0.5
            mobile = False
            if block in (37, 41):
                continue
        elif mob_coord > 0.5:
            required = 2
            hard = mob_hard > 0.5
            mobile = True
        else:
            continue
        if required not in (2, 3) or (block in PASSABLE and not mobile):
            continue
        if block in ORE_TOOL and tool < ORE_TOOL[block]:
            continue
        tile = (r, c)
        radius = 1 if mobile else 2
        health_floor = 5.0 if mobile else 3.5
        nearby = tuple(sorted(peer for peer, place in positions.items()
                              if stats[peer]['alive'] and stats[peer]['health'] >= health_floor
                              and _distance(place, tile) <= radius))
        if len(nearby) < required:
            continue
        plan = _assignment(obs, positions, nearby, tile, required)
        if plan is None:
            continue
        group, assigned, cost, max_cost = plan
        if agent_id not in group:
            continue
        signature = _signature(obs, r, c)
        if signature in blocked:
            continue
        channel = _channel(tile, block, required, group, positions, len(memory['comm']))
        signals = sum(1 for peer in group if peer != agent_id
                      and positions[peer] == assigned[peer]
                      and stats[peer]['comm'][channel])
        anchor = positions[group[0]]
        rank = (cost - (2.5 if hard else 0.0) - 2.0 * signals
                - (1.5 if memory.get('focus') == signature else 0.0),
                max_cost, 0 if hard else 1, r - anchor[0], c - anchor[1], block, group)
        if best is None or rank < best[0]:
            best = (rank, target, group, assigned, required, signature, channel)
    return best


def _handover_action(obs, mask, target, positions, agent_id, facing):
    r, c, block, _, _, _, _, active = target
    tile = (r, c)
    if block == 41:
        available = [a for a in BUILD_ACTIONS if a < len(mask) and mask[a]]
        if len(available) != 1:
            return None
        interaction = available[0]
    else:
        interaction = 5
    remaining = active * 15.0
    distance = _distance(positions[agent_id], tile)
    if distance == 1:
        direction = _toward(positions[agent_id], tile)
        need = 1 if facing == direction else 2
        if remaining + 0.05 < need:
            return None
        return interaction if facing == direction else direction
    if distance > 3:
        return None
    routes = []
    for _, dr, dc in MOVES:
        neighbor = (r + dr, c + dc)
        if not _clear(obs, neighbor, positions, agent_id):
            continue
        path = _path(obs, neighbor, positions, agent_id, limit=3)
        if not path:
            continue
        direction = _toward(neighbor, tile)
        need = len(path) + (0 if path[-1] == direction else 1) + 1
        if remaining + 0.05 >= need:
            routes.append((need, len(path), neighbor, path[0]))
    return min(routes)[3] if routes else None


def _act(local, memory):
    proposal = int(local['proposal'])
    obs = local['observation']
    mask = local['legal_mask']
    if len(obs) < DIRECTION + 4 or not memory.get('comm'):
        return {'action': proposal, 'memory': memory}
    step = int(local['step'])
    agent_id = memory['id']
    positions, targets = _scan(obs, agent_id)
    stats = _dashboard(obs, agent_id)
    facing = _facing(obs)
    memory['cool'] = [entry for entry in memory.get('cool', []) if entry[1] > step]
    pending = memory.get('own_pending')
    if pending is not None and pending[1] <= step:
        memory['own_pending'] = None
    last = memory.get('last_start')
    memory['last_start'] = None
    if last is not None and step == last[1] + 1:
        for target in targets:
            if target[7] > 0.001 and _signature(obs, target[0], target[1]) == last[0]:
                memory['own_pending'] = [last[0], step + 20]
                break

    def finish(action):
        if action is None or action < 0 or action >= len(mask) or not mask[action]:
            action = proposal
        if action in (5, 51, 52, 53) and facing:
            direction = next(((dr, dc) for move, dr, dc in MOVES if move == facing), None)
            if direction is not None:
                aimed = (4 + direction[0], 5 + direction[1])
                for target in targets:
                    if (target[0], target[1]) == aimed and target[3] < -0.001 and target[7] <= 0.001:
                        memory['last_start'] = [_signature(obs, *aimed), step]
                        break
        return {'action': action, 'memory': memory}

    if sum(bool(x) for x in mask) <= 1 or proposal in (18, 19):
        return finish(proposal)
    if stats[agent_id]['health'] < 3.5 or min(obs[INTR:INTR + 3]) < 0.15:
        return finish(proposal)

    handovers = []
    for target in targets:
        if target[3] >= -0.001 or target[7] <= 0.001:
            continue
        signature = _signature(obs, target[0], target[1])
        own = memory.get('own_pending')
        if own is not None and own[0] == signature:
            continue
        action = _handover_action(obs, mask, target, positions, agent_id, facing)
        if action is not None:
            handovers.append((target[7], _distance(positions[agent_id], target[:2]),
                              target[0], target[1], action))
    if handovers:
        memory['focus'] = None
        memory['age'] = 0
        return finish(min(handovers)[4])

    tool = round(obs[INV + 11] * 4)
    choice = _best_sync(obs, positions, stats, targets, agent_id, memory, tool)
    if choice is None:
        memory['focus'] = None
        memory['age'] = 0
        return finish(proposal)
    _, target, group, assigned, required, signature, channel = choice
    old_focus = memory.get('focus')
    if old_focus == signature:
        memory['age'] += 1
    else:
        memory['focus'] = signature
        memory['age'] = 1
    if memory['age'] > 10:
        memory['cool'] = (memory['cool'] + [[signature, step + 30]])[-8:]
        memory['focus'] = None
        memory['age'] = 0
        return finish(proposal)

    slot = assigned[agent_id]
    if positions[agent_id] != slot:
        path = _path(obs, slot, positions, agent_id)
        if not path:
            memory['cool'] = (memory['cool'] + [[signature, step + 30]])[-8:]
            return finish(proposal)
        return finish(path[0])
    direction = _toward(positions[agent_id], target[:2])
    if direction is None:
        return finish(proposal)
    if facing != direction:
        return finish(direction)
    if old_focus != signature and proposal == 5:
        return finish(proposal)
    ready = sum(1 for peer in group if positions[peer] == assigned[peer]
                and stats[peer]['comm'][channel])
    if ready >= required:
        return finish(5)
    return finish(memory['comm'][channel])


def act(local, memory):
    if not isinstance(memory, dict):
        memory = {}
    try:
        return _act(local, memory)
    except Exception:
        return {'action': int(local['proposal']), 'memory': memory}

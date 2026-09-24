"""Bounded, decentralized rendezvous for hard-sync resource gathering.

A native communication channel encodes the direction from the sender to
an adjacent target. Ready actors advertise; a visible quorum acts together
on the following turn. All other decisions use the frozen proposal.
"""

from collections import deque

ROWS = 9
COLS = 11
CHANNELS = 97
CENTER = 49
SPATIAL = 9603
INVENTORY = 9681
INTRINSICS = 9703
FACING = 9711
DIRECTIONS = ((0, 0), (0, -1), (0, 1), (-1, 0), (1, 0))
PASSABLE = frozenset((2, 6, 7, 13, 25, 26, 27))
PICK_REQUIRED = {5: 0, 4: 1, 8: 1, 9: 2, 10: 3, 21: 4, 22: 4}
MAX_ROUTE = 4
MAX_RENDEZVOUS = 12
FAILURE_COOLDOWN = 32


def initialize(agent_id, schema):
    return {
        'id': int(agent_id),
        'comm': list(schema.get('native_comm_action_ids') or []),
        'run': 0,
        'until': 0,
        'anchor': None,
        'shots': 0,
        'level': None,
    }


def _release(memory):
    memory['run'] = 0
    memory['anchor'] = None
    memory['shots'] = 0


def _neighbor(index, action):
    r, c = divmod(index, COLS)
    dr, dc = DIRECTIONS[action]
    r, c = r + dr, c + dc
    if 0 <= r < ROWS and 0 <= c < COLS:
        return r * COLS + c
    return None


def _distance(a, b):
    ar, ac = divmod(a, COLS)
    br, bc = divmod(b, COLS)
    return abs(ar - br) + abs(ac - bc)


def _observe(obs, agent_id):
    order = [agent_id] + [i for i in range(3) if i != agent_id]
    positions = {}
    alive = {}
    messages = {}
    for slot, identity in enumerate(order):
        start = SPATIAL + 18 * slot
        alive[identity] = obs[start + 1] > 0.5
        messages[identity] = tuple(obs[start + 14:start + 18])

    grid = []
    hostiles = []
    for index in range(ROWS * COLS):
        start = index * CHANNELS
        lit = obs[start + 96] > 0.5
        block = -1
        if lit:
            for b in range(42):
                if obs[start + b] > 0.5:
                    block = b
                    break
        occupants = []
        for slot, identity in enumerate(order):
            if obs[start + 87 + slot] > 0.5:
                positions[identity] = index
                occupants.append(identity)
        mob = any(obs[start + k] > 0.5 for k in range(47, 71))
        hostile = any(obs[start + k] > 0.5 for k in range(47, 55))
        hostile = hostile or any(obs[start + k] > 0.5 for k in range(63, 71))
        if hostile:
            hostiles.append(index)
        grid.append({
            'block': block,
            'occupants': occupants,
            'mob': mob,
            'coord': obs[start + 91],
            'soft': obs[start + 92] > 0.5,
            'pending': obs[start + 95],
        })
    for index, cell in enumerate(grid):
        cell['danger'] = any(_distance(index, h) <= 2 for h in hostiles)

    face = 0
    for action in range(1, 5):
        if obs[FACING + action - 1] > 0.5:
            face = action
            break
    return {
        'grid': grid,
        'positions': positions,
        'alive': alive,
        'messages': messages,
        'pick': int(round(obs[INVENTORY + 11] * 4.0)),
        'face': face,
        'level': obs[9727],
        'health': obs[SPATIAL],
        'food': obs[INTRINSICS],
        'drink': obs[INTRINSICS + 1],
        'energy': obs[INTRINSICS + 2],
    }


def _ground(cell):
    return cell['block'] in PASSABLE and not cell['mob'] and not cell['danger']


def _task(view, index):
    if index is None:
        return None
    grid = view['grid']
    cell = grid[index]
    required_pick = PICK_REQUIRED.get(cell['block'])
    if required_pick is None or view['pick'] < required_pick:
        return None
    if cell['coord'] <= 0 or cell['soft'] or cell['pending'] > 0:
        return None
    required = int(round(cell['coord'] * 3.0))
    if required not in (2, 3):
        return None
    if cell['mob'] or cell['occupants'] or cell['danger']:
        return None
    nearby = sum(
        1 for identity, position in view['positions'].items()
        if view['alive'].get(identity, False) and _distance(position, index) <= 5
    )
    if nearby < required:
        return None
    slots = 0
    for action in range(1, 5):
        position = _neighbor(index, action)
        if position is not None and _ground(grid[position]):
            slots += 1
    return required if slots >= required else None


def _route(view, target, agent_id):
    grid = view['grid']
    goals = {}
    for action in range(1, 5):
        position = _neighbor(target, action)
        if position is None or not _ground(grid[position]):
            continue
        if position != CENTER and grid[position]['occupants']:
            continue
        for facing in range(1, 5):
            if _neighbor(position, facing) == target:
                goals[position] = facing
                break
    if not goals:
        return None
    # Agent-dependent tie order reduces simultaneous claims on the same slot.
    actions = tuple(1 + ((k + agent_id) % 4) for k in range(4))
    queue = deque([(CENTER, 0, 0)])
    seen = {CENTER}
    while queue:
        position, distance, first = queue.popleft()
        if position in goals:
            return distance, first, goals[position]
        if distance >= MAX_ROUTE:
            continue
        for action in actions:
            nxt = _neighbor(position, action)
            if nxt is None or nxt in seen:
                continue
            cell = grid[nxt]
            if not _ground(cell) or cell['occupants']:
                continue
            seen.add(nxt)
            queue.append((nxt, distance + 1, first or action))
    return None


def act(local, memory):
    mask = local['legal_mask']
    proposal = int(local['proposal'])
    if not (0 <= proposal < len(mask) and mask[proposal]):
        proposal = next((i for i, legal in enumerate(mask) if legal), 0)
    obs = local['observation']
    step = int(local['step'])
    comm = memory['comm']

    def baseline():
        _release(memory)
        return {'action': proposal, 'memory': memory}

    if len(obs) != 9733 or len(mask) != 60 or len(comm) != 4:
        return baseline()
    if len(set(comm)) != 4 or any(not isinstance(a, int) or not 0 <= a < len(mask) for a in comm):
        return baseline()
    if not mask[5] or step < memory['until']:
        return baseline()

    view = _observe(obs, memory['id'])
    if memory['level'] != view['level']:
        _release(memory)
    memory['level'] = view['level']
    if (view['health'] < 0.5 or view['food'] <= 0.15 or
            view['drink'] <= 0.15 or view['energy'] <= 0.2 or
            view['grid'][CENTER]['danger']):
        return baseline()

    # Do not begin a rendezvous by interrupting survival, transfer, or travel.
    if not memory['run'] and proposal in (6, 17, 18, 19, 28, 29, 30, 31, 32, 33, 42, 43, 54, 55):
        return baseline()
    faced = _neighbor(CENTER, view['face']) if view['face'] else None
    if proposal == 5 and faced is not None:
        cell = view['grid'][faced]
        downed = any(not view['alive'].get(i, False) for i in cell['occupants'])
        if downed or cell['coord'] < 0 or cell['pending'] > 0:
            return baseline()

    # Messages are interpreted only when they identify an eligible adjacent
    # hard-sync resource at the sender's currently observed position.
    signals = {}
    for identity, position in view['positions'].items():
        if not view['alive'].get(identity, False):
            continue
        message = view['messages'][identity]
        channels = [k for k, value in enumerate(message) if value > 0.5]
        if len(channels) != 1:
            continue
        target = _neighbor(position, channels[0] + 1)
        if _task(view, target) is not None:
            signals.setdefault(target, set()).add(identity)

    choices = []
    for target, senders in signals.items():
        required = _task(view, target)
        route = _route(view, target, memory['id'])
        if route is None:
            continue
        # An established quorum will finish now; avoid chasing it from afar.
        if len(senders) >= required and (route[0] or view['face'] != route[2]):
            continue
        choices.append((0, -len(senders), min(senders), route[0], target, route, required))

    anchor = memory['anchor']
    if anchor is not None:
        target, block = anchor
        required = _task(view, target)
        if required is not None and view['grid'][target]['block'] == block:
            route = _route(view, target, memory['id'])
            if route is not None and route[0] == 0:
                choices.append((1, 0, memory['id'], 0, target, route, required))

    # New invitations originate from the frozen policy's own interaction
    # or blocked turn toward a hard resource, rather than a scripted tour.
    target = None
    if proposal == 5:
        target = faced
    elif proposal in (1, 2, 3, 4):
        target = _neighbor(CENTER, proposal)
    required = _task(view, target)
    if required is not None:
        route = _route(view, target, memory['id'])
        if route is not None and route[0] == 0:
            choices.append((2, 0, memory['id'], 0, target, route, required))

    if not choices:
        return baseline()
    choice = min(choices)
    target, route, required = choice[4], choice[5], choice[6]
    distance, first, facing = route
    key = [target, view['grid'][target]['block']]
    shots = memory['shots'] if anchor == key else 0
    run = memory['run'] + 1
    if run > MAX_RENDEZVOUS or (distance == 0 and shots >= 2):
        memory['until'] = step + FAILURE_COOLDOWN
        return baseline()

    if distance:
        action = first
    elif view['face'] != facing:
        # Resources are solid, so this sets facing without entering the tile.
        action = facing
    elif len(signals.get(target, ())) >= required:
        action = 5
    else:
        action = comm[facing - 1]

    if not (0 <= action < len(mask) and mask[action]):
        return baseline()
    memory['run'] = run
    # Retain egocentric coordinates only while stationary beside the target.
    # Approaching actors reacquire it from fresh native messages each turn.
    memory['anchor'] = key if distance == 0 else None
    memory['shots'] = shots + int(action == 5) if distance == 0 else 0
    return {'action': int(action), 'memory': memory}

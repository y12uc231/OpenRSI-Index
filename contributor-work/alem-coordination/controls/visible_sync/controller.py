"""Simple scripted control: align actors already beside one hard sync block.

This is an author-written heuristic, not a model-generated research result or
an optimal coordination algorithm. It reads only the official local vector.
"""


def initialize(agent_id, schema):
    return {'id': agent_id, 'compatible': schema['observation_size'] == 9733}


def act(local, memory):
    action = local['proposal']
    observation = local['observation']
    if not memory['compatible'] or observation[9603] < 0.4:
        return {'action': action, 'memory': memory}
    # Do not take control while hungry, thirsty, or exhausted.
    if min(observation[9703:9706]) < 0.3:
        return {'action': action, 'memory': memory}

    def cell(row, col):
        start = (row * 11 + col) * 97
        return observation[start:start + 97]

    # Teammate spatial identity channels reorder self first, then other IDs.
    order = [memory['id']] + [i for i in range(3) if i != memory['id']]
    positions = {}
    for row in range(9):
        for col in range(11):
            tile = cell(row, col)
            if tile[90] > 0.5:
                for slot in range(3):
                    if tile[87 + slot] > 0.5:
                        positions[order[slot]] = (row, col)
    if len(positions) < 2:
        return {'action': action, 'memory': memory}
    anchor = positions[min(positions)]
    targets = []
    directions = [(4, 4, 1), (4, 6, 2), (3, 5, 3), (5, 5, 4)]
    for row, col, face_action in directions:
        tile = cell(row, col)
        required = round(tile[91] * 3)
        if required < 2 or tile[92] > 0.5:
            continue
        # This control handles hard resource synchronization only. Construction
        # has separate resource costs and BUILD actions, so leave it to policy.
        if not any(tile[index] > 0.5 for index in (4, 5, 8, 9, 10, 21, 22)):
            continue
        adjacent = sum(abs(r - row) + abs(c - col) == 1 for r, c in positions.values())
        if adjacent >= required:
            targets.append((row - anchor[0], col - anchor[1], face_action))
    if targets:
        _, _, face_action = min(targets)
        facing = max(range(4), key=lambda i: observation[9711 + i]) + 1
        proposed = 5 if facing == face_action else face_action
        if local['legal_mask'][proposed]:
            action = proposed
    return {'action': action, 'memory': memory}

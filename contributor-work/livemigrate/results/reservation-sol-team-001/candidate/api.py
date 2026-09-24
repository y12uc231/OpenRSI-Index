import json


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _send(messages, node, body):
    messages.append({'to': node, 'body': body})


def _setup(conn, body):
    conn.execute('CREATE TABLE IF NOT EXISTS g_routes(sku TEXT PRIMARY KEY, owner TEXT NOT NULL, epoch INTEGER NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS g_requests(reservation_id TEXT PRIMARY KEY, lines_json TEXT NOT NULL, status TEXT NOT NULL, final_acked INTEGER NOT NULL DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS g_parts(reservation_id TEXT NOT NULL, node TEXT NOT NULL, part_json TEXT NOT NULL, prepared INTEGER NOT NULL DEFAULT 0, decided INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(reservation_id,node))')
    conn.execute('CREATE TABLE IF NOT EXISTS g_calls(call_id TEXT PRIMARY KEY, reservation_id TEXT NOT NULL, lines_json TEXT NOT NULL, origin TEXT NOT NULL, conflict INTEGER NOT NULL, acked INTEGER NOT NULL DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS g_decisions(reservation_id TEXT PRIMARY KEY, lines_json TEXT NOT NULL, state TEXT NOT NULL)')
    conn.execute('CREATE VIEW IF NOT EXISTS audit_decisions AS SELECT reservation_id,lines_json,state FROM g_decisions')
    for sku in body['capacities']:
        owner = body.get('routing', {}).get(sku, 'source')
        conn.execute('INSERT OR IGNORE INTO g_routes(sku,owner,epoch) VALUES(?,?,0)', (sku, owner))


def _record_call(conn, body, origin):
    call_id = body['call_id']
    if conn.execute('SELECT 1 FROM g_calls WHERE call_id=?', (call_id,)).fetchone():
        return
    rid = body['reservation_id']
    raw = _json(body['lines'])
    old = conn.execute('SELECT lines_json FROM g_requests WHERE reservation_id=?', (rid,)).fetchone()
    conflict = old is not None and old[0] != raw
    if old is None:
        conn.execute('INSERT INTO g_requests(reservation_id,lines_json,status) VALUES(?,?,?)', (rid, raw, 'pending'))
    conn.execute('INSERT INTO g_calls(call_id,reservation_id,lines_json,origin,conflict) VALUES(?,?,?,?,?)', (call_id, rid, raw, origin, int(conflict)))


def _ensure_parts(conn, rid, lines):
    if conn.execute('SELECT 1 FROM g_parts WHERE reservation_id=? LIMIT 1', (rid,)).fetchone():
        return
    groups = {}
    for sku, qty in lines.items():
        row = conn.execute('SELECT owner FROM g_routes WHERE sku=?', (sku,)).fetchone()
        owner = row[0] if row else 'source'
        groups.setdefault(owner, {})[sku] = qty
    for node, part in groups.items():
        conn.execute('INSERT INTO g_parts(reservation_id,node,part_json) VALUES(?,?,?)', (rid, node, _json(part)))


def _decide(conn, rid, status):
    row = conn.execute('SELECT lines_json,status FROM g_requests WHERE reservation_id=?', (rid,)).fetchone()
    if row is None or row[1] != 'pending':
        return
    state = 'commit' if status == 'committed' else 'abort'
    conn.execute('INSERT INTO g_decisions(reservation_id,lines_json,state) VALUES(?,?,?)', (rid, row[0], state))
    conn.execute('UPDATE g_requests SET status=? WHERE reservation_id=?', (status, rid))


def _maybe_commit(conn, rid, lines):
    rows = conn.execute('SELECT node,part_json,prepared FROM g_parts WHERE reservation_id=?', (rid,)).fetchall()
    if not rows or any(not row[2] for row in rows):
        return
    covered = {}
    for _, raw, _ in rows:
        for sku, qty in json.loads(raw).items():
            if sku in covered:
                return
            covered[sku] = qty
    if covered == lines:
        _decide(conn, rid, 'committed')


def _route(conn, sku, owner, epoch):
    old = conn.execute('SELECT epoch FROM g_routes WHERE sku=?', (sku,)).fetchone()
    if old is None:
        conn.execute('INSERT INTO g_routes(sku,owner,epoch) VALUES(?,?,?)', (sku, owner, epoch))
    elif epoch > old[0]:
        conn.execute('UPDATE g_routes SET owner=?,epoch=? WHERE sku=?', (owner, epoch, sku))


def _redirect(conn, rid, node, route):
    row = conn.execute('SELECT part_json,prepared FROM g_parts WHERE reservation_id=? AND node=?', (rid, node)).fetchone()
    if row is None or row[1]:
        return
    part = json.loads(row[0])
    moved = {sku: owner for sku, owner in route.items() if sku in part and owner in ('A', 'B') and owner != node}
    if not moved:
        return
    groups = {}
    for sku, owner in moved.items():
        groups.setdefault(owner, {})[sku] = part[sku]
    for owner in groups:
        existing = conn.execute('SELECT prepared FROM g_parts WHERE reservation_id=? AND node=?', (rid, owner)).fetchone()
        if existing is not None and existing[0]:
            return
    for sku, owner in moved.items():
        current = conn.execute('SELECT owner,epoch FROM g_routes WHERE sku=?', (sku,)).fetchone()
        if current is None:
            _route(conn, sku, owner, 1)
        elif current[0] == 'source':
            _route(conn, sku, owner, current[1] + 1)
    remaining = {sku: qty for sku, qty in part.items() if sku not in moved}
    if remaining:
        conn.execute('UPDATE g_parts SET part_json=? WHERE reservation_id=? AND node=?', (_json(remaining), rid, node))
    else:
        conn.execute('DELETE FROM g_parts WHERE reservation_id=? AND node=?', (rid, node))
    for owner, addition in groups.items():
        existing = conn.execute('SELECT part_json FROM g_parts WHERE reservation_id=? AND node=?', (rid, owner)).fetchone()
        if existing is None:
            conn.execute('INSERT INTO g_parts(reservation_id,node,part_json) VALUES(?,?,?)', (rid, owner, _json(addition)))
        else:
            combined = json.loads(existing[0])
            combined.update(addition)
            conn.execute('UPDATE g_parts SET part_json=? WHERE reservation_id=? AND node=?', (_json(combined), rid, owner))


def _reroute_pending_source_parts(conn, sku, owner, epoch):
    current = conn.execute('SELECT owner,epoch FROM g_routes WHERE sku=?', (sku,)).fetchone()
    if current is None or current[0] != owner or current[1] < epoch:
        return
    rows = conn.execute('SELECT p.reservation_id,p.part_json,p.prepared FROM g_parts p JOIN g_requests r ON r.reservation_id=p.reservation_id WHERE p.node=? AND r.status=? ORDER BY r.rowid', ('source', 'pending')).fetchall()
    for rid, raw, prepared in rows:
        if not prepared and sku in json.loads(raw):
            _redirect(conn, rid, 'source', {sku: owner})


def _participant_result(conn, node, body):
    rid = body.get('reservation_id')
    row = conn.execute('SELECT status FROM g_requests WHERE reservation_id=?', (rid,)).fetchone()
    if row is None:
        return
    status = row[0]
    op = body.get('op')
    if op == 'decided':
        expected = 'commit' if status == 'committed' else 'abort' if status == 'out_of_stock' else None
        if expected == body.get('decision'):
            conn.execute('UPDATE g_parts SET decided=1 WHERE reservation_id=? AND node=?', (rid, node))
        return
    if status != 'pending':
        return
    part = conn.execute('SELECT 1 FROM g_parts WHERE reservation_id=? AND node=?', (rid, node)).fetchone()
    if part is None:
        return
    if op == 'redirect' and node == 'source':
        _redirect(conn, rid, node, body.get('route', {}))
    elif op == 'prepared':
        conn.execute('UPDATE g_parts SET prepared=1 WHERE reservation_id=? AND node=?', (rid, node))
    elif op == 'rejected' and body.get('reason') == 'out_of_stock':
        _decide(conn, rid, 'out_of_stock')


def _admit_pending(conn):
    # Earlier unresolved bundles keep admission priority on all their SKUs.
    # This prevents split bundles from each holding stock the other needs.
    waiting_skus = set()
    admitted = set()
    rows = conn.execute('SELECT reservation_id,lines_json FROM g_requests WHERE status=? ORDER BY rowid', ('pending',)).fetchall()
    for rid, raw in rows:
        lines = json.loads(raw)
        skus = set(lines)
        if not waiting_skus.isdisjoint(skus):
            waiting_skus.update(skus)
            continue
        _ensure_parts(conn, rid, lines)
        _maybe_commit(conn, rid, lines)
        state = conn.execute('SELECT status FROM g_requests WHERE reservation_id=?', (rid,)).fetchone()[0]
        if state == 'pending':
            admitted.add(rid)
            waiting_skus.update(skus)
    return admitted


def _drive(conn, messages, replies):
    admitted = _admit_pending(conn)
    requests = conn.execute('SELECT reservation_id,lines_json,status,final_acked FROM g_requests ORDER BY rowid').fetchall()
    for rid, raw, status, final_acked in requests:
        lines = json.loads(raw)
        parts = conn.execute('SELECT node,part_json,prepared,decided FROM g_parts WHERE reservation_id=? ORDER BY node', (rid,)).fetchall()
        if status == 'pending':
            if rid in admitted:
                for node, part_raw, prepared, _ in parts:
                    if not prepared:
                        _send(messages, node, {'op': 'prepare', 'reservation_id': rid, 'lines': lines, 'part_lines': json.loads(part_raw)})
        else:
            decision = 'commit' if status == 'committed' else 'abort'
            for node, part_raw, _, decided in parts:
                if not decided:
                    _send(messages, node, {'op': 'decide', 'reservation_id': rid, 'lines': lines, 'part_lines': json.loads(part_raw), 'decision': decision})
            if not final_acked:
                _send(messages, 'source', {'op': 'final', 'reservation_id': rid, 'lines': lines, 'status': status})
    calls = conn.execute('SELECT call_id,reservation_id,lines_json,conflict FROM g_calls WHERE acked=0 ORDER BY rowid').fetchall()
    for call_id, rid, raw, conflict in calls:
        if conflict:
            status = 'idempotency_conflict'
        else:
            row = conn.execute('SELECT status FROM g_requests WHERE reservation_id=?', (rid,)).fetchone()
            if row is None or row[0] == 'pending':
                continue
            status = row[0]
            if status == 'out_of_stock':
                unfinished = conn.execute('SELECT 1 FROM g_parts WHERE reservation_id=? AND decided=0 LIMIT 1', (rid,)).fetchone()
                if unfinished:
                    continue
        replies.append({'call_id': call_id, 'reservation_id': rid, 'status': status, 'lines': json.loads(raw)})


def on_message(conn, message):
    body = message['body']
    src = message['src']
    messages = []
    replies = []
    if src == 'driver':
        kind = body.get('kind')
        if kind == 'init':
            _setup(conn, body)
        elif kind == 'client':
            _record_call(conn, body, 'gateway')
        elif kind == 'reply_ack':
            conn.execute('UPDATE g_calls SET acked=1 WHERE call_id=?', (body['call_id'],))
    elif src == 'source':
        op = body.get('op')
        if op == 'client':
            _record_call(conn, body, 'source')
        elif op == 'route':
            _route(conn, body['sku'], body['owner'], body['epoch'])
            _reroute_pending_source_parts(conn, body['sku'], body['owner'], body['epoch'])
            _send(messages, 'source', {'op': 'route_ack', 'sku': body['sku'], 'epoch': body['epoch']})
        elif op == 'final_ack':
            conn.execute('UPDATE g_requests SET final_acked=1 WHERE reservation_id=?', (body['reservation_id'],))
        elif op in ('prepared', 'rejected', 'retry', 'redirect', 'decided'):
            _participant_result(conn, src, body)
    elif src in ('A', 'B') and body.get('op') in ('prepared', 'rejected', 'retry', 'redirect', 'decided'):
        _participant_result(conn, src, body)
    _drive(conn, messages, replies)
    return {'messages': messages, 'replies': replies}

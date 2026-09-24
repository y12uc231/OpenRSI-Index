import json
import legacy


def _enc(lines):
    return legacy.fingerprint(lines)


def _send(messages, to, body):
    messages.append({'to': to, 'body': body})


def _answer(messages, rid, op, reason=None, decision=None, route=None):
    body = {'op': op, 'reservation_id': rid, 'participant': 'source'}
    if reason is not None:
        body['reason'] = reason
    if decision is not None:
        body['decision'] = decision
    if route is not None:
        body['route'] = route
    _send(messages, 'gateway', body)


def _setup(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS bridge_calls(call_id TEXT PRIMARY KEY, reservation_id TEXT NOT NULL, lines_json TEXT NOT NULL, acked INTEGER NOT NULL DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS bridge_participants(reservation_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, lines_json TEXT NOT NULL, part_json TEXT NOT NULL, state TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS source_transfers(sku TEXT PRIMARY KEY, destination TEXT NOT NULL, epoch INTEGER NOT NULL, phase TEXT NOT NULL, route_acked INTEGER NOT NULL DEFAULT 0)')
    conn.execute('CREATE INDEX IF NOT EXISTS bridge_legacy_holds_sku_state ON legacy_holds(sku,state)')
    conn.execute('''CREATE VIEW IF NOT EXISTS audit_inventory AS SELECT sku,total,available,epoch,CASE WHEN active=1 THEN 'active' ELSE 'fenced' END AS authority FROM legacy_stock''')
    conn.execute('CREATE VIEW IF NOT EXISTS audit_holds AS SELECT reservation_id,sku,qty,state FROM legacy_holds')


def _receipt(conn, rid, lines, status):
    if status not in ('committed', 'out_of_stock'):
        return False
    encoded = _enc(lines)
    old = conn.execute('SELECT fingerprint,status FROM legacy_requests WHERE reservation_id=?', (rid,)).fetchone()
    if old is not None:
        return old[0] == encoded and old[1] == status
    conn.execute('INSERT INTO legacy_requests(reservation_id,fingerprint,status,lines_json) VALUES(?,?,?,?)', (rid, encoded, status, encoded))
    return True


def _prepare(conn, body, messages):
    rid = body['reservation_id']
    lines = body['lines']
    part = body['part_lines']
    if not part or any(lines.get(sku) != qty for sku, qty in part.items()):
        _answer(messages, rid, 'rejected', reason='idempotency_conflict')
        return
    encoded = _enc(lines)
    part_encoded = _enc(part)
    old = conn.execute('SELECT fingerprint,part_json,state FROM bridge_participants WHERE reservation_id=?', (rid,)).fetchone()
    if old is not None:
        if old[0] != encoded or old[1] != part_encoded:
            _answer(messages, rid, 'rejected', reason='idempotency_conflict')
        elif old[2] in ('prepared', 'committed'):
            _answer(messages, rid, 'prepared')
        elif old[2] == 'rejected':
            _answer(messages, rid, 'rejected', reason='out_of_stock')
        else:
            _answer(messages, rid, 'rejected', reason='aborted')
        return
    receipt = conn.execute('SELECT fingerprint FROM legacy_requests WHERE reservation_id=?', (rid,)).fetchone()
    if receipt is not None:
        reason = 'already_finished' if receipt[0] == encoded else 'idempotency_conflict'
        _answer(messages, rid, 'rejected', reason=reason)
        return
    redirect = {}
    moving = False
    inactive = False
    for sku in part:
        stock = conn.execute('SELECT active FROM legacy_stock WHERE sku=?', (sku,)).fetchone()
        transfer = conn.execute('SELECT destination FROM source_transfers WHERE sku=?', (sku,)).fetchone()
        if stock is None:
            inactive = True
        elif not stock[0]:
            if transfer is None:
                inactive = True
            else:
                redirect[sku] = transfer[0]
        elif transfer is not None:
            moving = True
    if redirect:
        _answer(messages, rid, 'redirect', route=redirect)
        return
    if moving or inactive:
        _answer(messages, rid, 'retry', reason='moving' if moving else 'inactive')
        return
    insufficient = []
    for sku, qty in part.items():
        available = conn.execute('SELECT available FROM legacy_stock WHERE sku=?', (sku,)).fetchone()[0]
        if available < qty:
            insufficient.append(sku)
    if insufficient:
        tentative = any(conn.execute('''SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared' LIMIT 1''', (sku,)).fetchone() for sku in insufficient)
        if tentative:
            _answer(messages, rid, 'retry', reason='tentative_hold')
        else:
            conn.execute('INSERT INTO bridge_participants VALUES(?,?,?,?,?)', (rid, encoded, encoded, part_encoded, 'rejected'))
            _answer(messages, rid, 'rejected', reason='out_of_stock')
        return
    for sku, qty in part.items():
        conn.execute('UPDATE legacy_stock SET available=available-? WHERE sku=?', (qty, sku))
        conn.execute('''INSERT INTO legacy_holds(reservation_id,sku,qty,state) VALUES(?,?,?,'prepared')''', (rid, sku, qty))
    conn.execute('INSERT INTO bridge_participants VALUES(?,?,?,?,?)', (rid, encoded, encoded, part_encoded, 'prepared'))
    _answer(messages, rid, 'prepared')


def _decide(conn, body, messages):
    rid = body['reservation_id']
    lines = body['lines']
    part = body['part_lines']
    decision = body['decision']
    if decision not in ('commit', 'abort'):
        return
    encoded = _enc(lines)
    part_encoded = _enc(part)
    old = conn.execute('SELECT fingerprint,part_json,state FROM bridge_participants WHERE reservation_id=?', (rid,)).fetchone()
    if old is not None and (old[0] != encoded or old[1] != part_encoded):
        _answer(messages, rid, 'rejected', reason='idempotency_conflict')
        return
    status = 'committed' if decision == 'commit' else 'out_of_stock'
    receipt = conn.execute('SELECT fingerprint,status FROM legacy_requests WHERE reservation_id=?', (rid,)).fetchone()
    if receipt is not None and (receipt[0] != encoded or receipt[1] != status):
        _answer(messages, rid, 'rejected', reason='idempotency_conflict')
        return
    if decision == 'commit':
        if old is None or old[2] not in ('prepared', 'committed'):
            _answer(messages, rid, 'retry', reason='missing_prepare')
            return
        if old[2] == 'prepared':
            conn.execute('''UPDATE legacy_holds SET state='committed' WHERE reservation_id=? AND state='prepared' ''', (rid,))
            conn.execute('''UPDATE bridge_participants SET state='committed' WHERE reservation_id=?''', (rid,))
    else:
        if old is not None and old[2] == 'committed':
            _answer(messages, rid, 'rejected', reason='already_committed')
            return
        if old is None:
            conn.execute('INSERT INTO bridge_participants VALUES(?,?,?,?,?)', (rid, encoded, encoded, part_encoded, 'released'))
        elif old[2] == 'prepared':
            held = conn.execute('''SELECT sku,qty FROM legacy_holds WHERE reservation_id=? AND state='prepared' ''', (rid,)).fetchall()
            for sku, qty in held:
                conn.execute('UPDATE legacy_stock SET available=available+? WHERE sku=?', (qty, sku))
            conn.execute('''UPDATE legacy_holds SET state='released' WHERE reservation_id=? AND state='prepared' ''', (rid,))
            conn.execute('''UPDATE bridge_participants SET state='released' WHERE reservation_id=?''', (rid,))
        elif old[2] == 'rejected':
            conn.execute('''UPDATE bridge_participants SET state='released' WHERE reservation_id=?''', (rid,))
    _receipt(conn, rid, lines, status)
    _answer(messages, rid, 'decided', decision=decision)


def _progress(conn, messages):
    transfers = conn.execute('SELECT sku,destination,epoch,phase,route_acked FROM source_transfers ORDER BY sku').fetchall()
    for sku, destination, epoch, phase, route_acked in transfers:
        if phase == 'waiting':
            pending = conn.execute('''SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared' LIMIT 1''', (sku,)).fetchone()
            if pending is not None:
                continue
            conn.execute('UPDATE legacy_stock SET active=0 WHERE sku=? AND active=1', (sku,))
            conn.execute('''UPDATE source_transfers SET phase='fenced' WHERE sku=?''', (sku,))
            phase = 'fenced'
        if phase == 'fenced':
            stock = conn.execute('SELECT total,available FROM legacy_stock WHERE sku=?', (sku,)).fetchone()
            holds = [{'reservation_id': row[0], 'qty': row[1], 'state': 'committed'} for row in conn.execute('''SELECT reservation_id,qty FROM legacy_holds WHERE sku=? AND state='committed' ORDER BY reservation_id''', (sku,))]
            _send(messages, destination, {'op': 'install', 'sku': sku, 'epoch': epoch, 'total': stock[0], 'available': stock[1], 'holds': holds})
        if phase in ('fenced', 'done') and not route_acked:
            _send(messages, 'gateway', {'op': 'route', 'sku': sku, 'owner': destination, 'epoch': epoch})
    for call_id, rid, raw in conn.execute('SELECT call_id,reservation_id,lines_json FROM bridge_calls WHERE acked=0 ORDER BY call_id'):
        _send(messages, 'gateway', {'op': 'client', 'call_id': call_id, 'reservation_id': rid, 'lines': json.loads(raw), 'origin': 'source'})


def on_message(conn, message):
    src = message['src']
    body = message['body']
    messages = []
    if src == 'driver':
        kind = body.get('kind')
        if kind == 'init':
            _setup(conn)
        elif kind == 'client':
            conn.execute('INSERT OR IGNORE INTO bridge_calls(call_id,reservation_id,lines_json) VALUES(?,?,?)', (body['call_id'], body['reservation_id'], _enc(body['lines'])))
        elif kind == 'reply_ack':
            conn.execute('UPDATE bridge_calls SET acked=1 WHERE call_id=?', (body['call_id'],))
        elif kind == 'move':
            sku = body['sku']
            if conn.execute('SELECT 1 FROM source_transfers WHERE sku=?', (sku,)).fetchone() is None:
                stock = conn.execute('SELECT epoch,active FROM legacy_stock WHERE sku=?', (sku,)).fetchone()
                if stock is not None and stock[1]:
                    conn.execute('''INSERT INTO source_transfers(sku,destination,epoch,phase) VALUES(?,?,?,'waiting')''', (sku, body['destination'], stock[0] + 1))
    elif src == 'gateway':
        op = body.get('op')
        if op == 'prepare':
            _prepare(conn, body, messages)
        elif op == 'decide':
            _decide(conn, body, messages)
        elif op == 'route_ack':
            conn.execute('''UPDATE source_transfers SET route_acked=1 WHERE sku=? AND epoch=? AND phase IN ('fenced','done')''', (body['sku'], body['epoch']))
        elif op == 'final':
            if _receipt(conn, body['reservation_id'], body['lines'], body['status']):
                _send(messages, 'gateway', {'op': 'final_ack', 'reservation_id': body['reservation_id']})
    elif src in ('A', 'B') and body.get('op') == 'activated':
        row = conn.execute('SELECT destination,epoch,phase FROM source_transfers WHERE sku=?', (body['sku'],)).fetchone()
        if row is not None and row[0] == src and row[1] == body['epoch'] and row[2] in ('fenced', 'done'):
            conn.execute('''UPDATE source_transfers SET phase='done' WHERE sku=?''', (body['sku'],))
    _progress(conn, messages)
    return {'messages': messages, 'replies': []}

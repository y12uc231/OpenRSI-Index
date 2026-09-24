import json


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _send(messages, to, body):
    messages.append({'to': to, 'body': body})


def _setup(conn, body):
    conn.execute('CREATE TABLE IF NOT EXISTS owner_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS owner_stock(sku TEXT PRIMARY KEY, total INTEGER NOT NULL, available INTEGER NOT NULL, epoch INTEGER NOT NULL, authority TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS owner_holds(reservation_id TEXT NOT NULL, sku TEXT NOT NULL, qty INTEGER NOT NULL, state TEXT NOT NULL, PRIMARY KEY(reservation_id,sku))')
    conn.execute('CREATE TABLE IF NOT EXISTS owner_participants(reservation_id TEXT PRIMARY KEY, lines_json TEXT NOT NULL, part_json TEXT NOT NULL, state TEXT NOT NULL)')
    conn.execute('CREATE INDEX IF NOT EXISTS owner_holds_by_sku_state ON owner_holds(sku,state)')
    conn.execute('CREATE VIEW IF NOT EXISTS audit_inventory AS SELECT sku,total,available,epoch,authority FROM owner_stock')
    conn.execute('CREATE VIEW IF NOT EXISTS audit_holds AS SELECT reservation_id,sku,qty,state FROM owner_holds')
    conn.execute('INSERT OR IGNORE INTO owner_meta(key,value) VALUES(?,?)', ('node_id', body['node_id']))


def _answer(conn, messages, reservation_id, op, reason=None, decision=None):
    node = conn.execute('SELECT value FROM owner_meta WHERE key=?', ('node_id',)).fetchone()[0]
    body = {'op': op, 'reservation_id': reservation_id, 'participant': node}
    if reason is not None:
        body['reason'] = reason
    if decision is not None:
        body['decision'] = decision
    _send(messages, 'gateway', body)


def _install(conn, body, messages):
    sku = body['sku']
    epoch = body['epoch']
    old = conn.execute('SELECT epoch,authority FROM owner_stock WHERE sku=?', (sku,)).fetchone()
    if old is not None:
        if old[0] == epoch and old[1] == 'active':
            _send(messages, 'source', {'op': 'activated', 'sku': sku, 'epoch': epoch})
        return
    total = body['total']
    available = body['available']
    holds = body['holds']
    if epoch <= 0 or total < 0 or available < 0:
        return
    if any(item['state'] != 'committed' or item['qty'] <= 0 for item in holds):
        return
    if len({item['reservation_id'] for item in holds}) != len(holds):
        return
    if available + sum(item['qty'] for item in holds) != total:
        return
    conn.execute('INSERT INTO owner_stock(sku,total,available,epoch,authority) VALUES(?,?,?,?,?)', (sku, total, available, epoch, 'active'))
    for item in holds:
        conn.execute('INSERT INTO owner_holds(reservation_id,sku,qty,state) VALUES(?,?,?,?)', (item['reservation_id'], sku, item['qty'], 'committed'))
    _send(messages, 'source', {'op': 'activated', 'sku': sku, 'epoch': epoch})


def _prepare(conn, body, messages):
    rid = body['reservation_id']
    lines = body['lines']
    part = body['part_lines']
    if not part or any(lines.get(sku) != qty for sku, qty in part.items()):
        _answer(conn, messages, rid, 'rejected', 'idempotency_conflict')
        return
    encoded = _json(lines)
    part_encoded = _json(part)
    old = conn.execute('SELECT lines_json,part_json,state FROM owner_participants WHERE reservation_id=?', (rid,)).fetchone()
    if old is not None:
        if old[0] != encoded or old[1] != part_encoded:
            _answer(conn, messages, rid, 'rejected', 'idempotency_conflict')
        elif old[2] in ('prepared', 'committed'):
            _answer(conn, messages, rid, 'prepared')
        elif old[2] == 'rejected':
            _answer(conn, messages, rid, 'rejected', 'out_of_stock')
        else:
            _answer(conn, messages, rid, 'rejected', 'aborted')
        return
    insufficient = []
    for sku, qty in part.items():
        stock = conn.execute('SELECT available,authority FROM owner_stock WHERE sku=?', (sku,)).fetchone()
        if stock is None or stock[1] != 'active':
            _answer(conn, messages, rid, 'retry', 'inactive')
            return
        if stock[0] < qty:
            insufficient.append(sku)
    if insufficient:
        tentative = any(conn.execute('SELECT 1 FROM owner_holds WHERE sku=? AND state=? LIMIT 1', (sku, 'prepared')).fetchone() for sku in insufficient)
        if tentative:
            _answer(conn, messages, rid, 'retry', 'tentative_hold')
        else:
            conn.execute('INSERT INTO owner_participants(reservation_id,lines_json,part_json,state) VALUES(?,?,?,?)', (rid, encoded, part_encoded, 'rejected'))
            _answer(conn, messages, rid, 'rejected', 'out_of_stock')
        return
    for sku, qty in part.items():
        conn.execute('UPDATE owner_stock SET available=available-? WHERE sku=?', (qty, sku))
        conn.execute('INSERT INTO owner_holds(reservation_id,sku,qty,state) VALUES(?,?,?,?)', (rid, sku, qty, 'prepared'))
    conn.execute('INSERT INTO owner_participants(reservation_id,lines_json,part_json,state) VALUES(?,?,?,?)', (rid, encoded, part_encoded, 'prepared'))
    _answer(conn, messages, rid, 'prepared')


def _decide(conn, body, messages):
    rid = body['reservation_id']
    encoded = _json(body['lines'])
    part_encoded = _json(body['part_lines'])
    decision = body['decision']
    old = conn.execute('SELECT lines_json,part_json,state FROM owner_participants WHERE reservation_id=?', (rid,)).fetchone()
    if old is not None and (old[0] != encoded or old[1] != part_encoded):
        _answer(conn, messages, rid, 'rejected', 'idempotency_conflict')
        return
    if decision == 'commit':
        if old is None or old[2] not in ('prepared', 'committed'):
            _answer(conn, messages, rid, 'retry', 'missing_prepare')
            return
        if old[2] == 'prepared':
            conn.execute('UPDATE owner_holds SET state=? WHERE reservation_id=? AND state=?', ('committed', rid, 'prepared'))
            conn.execute('UPDATE owner_participants SET state=? WHERE reservation_id=?', ('committed', rid))
    elif decision == 'abort':
        if old is None:
            conn.execute('INSERT INTO owner_participants(reservation_id,lines_json,part_json,state) VALUES(?,?,?,?)', (rid, encoded, part_encoded, 'released'))
        elif old[2] == 'committed':
            _answer(conn, messages, rid, 'rejected', 'already_committed')
            return
        elif old[2] == 'prepared':
            held = conn.execute('SELECT sku,qty FROM owner_holds WHERE reservation_id=? AND state=?', (rid, 'prepared')).fetchall()
            for sku, qty in held:
                conn.execute('UPDATE owner_stock SET available=available+? WHERE sku=?', (qty, sku))
            conn.execute('UPDATE owner_holds SET state=? WHERE reservation_id=? AND state=?', ('released', rid, 'prepared'))
            conn.execute('UPDATE owner_participants SET state=? WHERE reservation_id=?', ('released', rid))
        elif old[2] == 'rejected':
            conn.execute('UPDATE owner_participants SET state=? WHERE reservation_id=?', ('released', rid))
    else:
        return
    _answer(conn, messages, rid, 'decided', decision=decision)


def on_message(conn, message):
    src = message['src']
    body = message['body']
    messages = []
    if src == 'driver':
        if body.get('kind') == 'init':
            _setup(conn, body)
    elif src == 'source' and body.get('op') == 'install':
        _install(conn, body, messages)
    elif src == 'gateway':
        if body.get('op') == 'prepare':
            _prepare(conn, body, messages)
        elif body.get('op') == 'decide':
            _decide(conn, body, messages)
    return {'messages': messages, 'replies': []}

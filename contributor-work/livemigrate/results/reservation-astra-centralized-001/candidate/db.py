import json
import sqlite3
import legacy


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _send(out, to, op, **fields):
    body = {'op': op}
    body.update(fields)
    out.append({'to': to, 'body': body})


def _setup(conn):
    statements = [
        'CREATE TABLE IF NOT EXISTS bridge_calls(call_id TEXT PRIMARY KEY,rid TEXT NOT NULL,fp TEXT NOT NULL,acked INTEGER NOT NULL DEFAULT 0)',
        "CREATE TABLE IF NOT EXISTS bridge_parts(rid TEXT NOT NULL,sku TEXT NOT NULL,qty INTEGER NOT NULL,fp TEXT NOT NULL,decision TEXT NOT NULL DEFAULT '',PRIMARY KEY(rid,sku))",
        'CREATE TABLE IF NOT EXISTS bridge_routed(rid TEXT PRIMARY KEY,fp TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS bridge_moves(sku TEXT PRIMARY KEY,destination TEXT NOT NULL,state TEXT NOT NULL,payload TEXT)',
        "CREATE VIEW IF NOT EXISTS audit_inventory AS SELECT sku,total,available,epoch,CASE WHEN active=1 THEN 'active' ELSE 'fenced' END AS authority FROM legacy_stock",
        'CREATE VIEW IF NOT EXISTS audit_holds AS SELECT reservation_id,sku,qty,state FROM legacy_holds'
    ]
    for statement in statements:
        conn.execute(statement)


def _vote(out, body, vote, **extra):
    _send(out, 'gateway', 'vote', rid=body['rid'], sku=body['sku'], fp=body['fp'], vote=vote, **extra)


def _prepare(conn, body, out):
    rid, sku, qty, fp = body['rid'], body['sku'], body['qty'], body['fp']
    part = conn.execute('SELECT * FROM bridge_parts WHERE rid=? AND sku=?', (rid, sku)).fetchone()
    receipt = conn.execute('SELECT fingerprint,status FROM legacy_requests WHERE reservation_id=?', (rid,)).fetchone()
    if receipt is not None and receipt['fingerprint'] != fp:
        return
    if part is not None and (part['fp'] != fp or part['qty'] != qty):
        return
    if receipt is not None and receipt['status'] == 'out_of_stock':
        _vote(out, body, 'no')
        return
    if part is not None and part['decision'] == 'abort':
        _vote(out, body, 'no')
        return
    hold = conn.execute('SELECT * FROM legacy_holds WHERE reservation_id=? AND sku=?', (rid, sku)).fetchone()
    if hold is not None:
        if hold['qty'] != qty:
            return
        _vote(out, body, 'yes' if hold['state'] in ('prepared', 'committed') else 'no')
        return
    if part is not None and part['decision'] == 'commit':
        _vote(out, body, 'wait')
        return
    stock = conn.execute('SELECT * FROM legacy_stock WHERE sku=?', (sku,)).fetchone()
    if stock is None:
        _vote(out, body, 'wait')
        return
    move = conn.execute('SELECT * FROM bridge_moves WHERE sku=?', (sku,)).fetchone()
    if not stock['active']:
        if move is not None and move['payload'] is not None:
            payload = json.loads(move['payload'])
            _vote(out, body, 'redirect', destination=move['destination'], epoch=payload['epoch'])
        else:
            _vote(out, body, 'wait')
        return
    tentative = conn.execute("SELECT COALESCE(SUM(qty),0) FROM legacy_holds WHERE sku=? AND state='prepared'", (sku,)).fetchone()[0]
    if stock['available'] + tentative < qty:
        _vote(out, body, 'no')
        return
    if stock['available'] < qty or (move is not None and move['state'] == 'waiting'):
        _vote(out, body, 'wait')
        return
    conn.execute("INSERT OR IGNORE INTO bridge_parts(rid,sku,qty,fp,decision) VALUES(?,?,?,?,'')", (rid, sku, qty, fp))
    conn.execute('UPDATE legacy_stock SET available=available-? WHERE sku=?', (qty, sku))
    conn.execute("INSERT INTO legacy_holds(reservation_id,sku,qty,state) VALUES(?,?,?,'prepared')", (rid, sku, qty))
    _vote(out, body, 'yes')


def _finish(conn, body, out):
    rid, sku, qty, fp = body['rid'], body['sku'], body['qty'], body['fp']
    decision = body['decision']
    if decision not in ('commit', 'abort'):
        return
    part = conn.execute('SELECT * FROM bridge_parts WHERE rid=? AND sku=?', (rid, sku)).fetchone()
    if part is not None:
        if part['fp'] != fp or part['qty'] != qty:
            return
        if part['decision'] and part['decision'] != decision:
            return
    receipt = conn.execute('SELECT fingerprint FROM legacy_requests WHERE reservation_id=?', (rid,)).fetchone()
    if receipt is not None and receipt['fingerprint'] != fp:
        return
    hold = conn.execute('SELECT * FROM legacy_holds WHERE reservation_id=? AND sku=?', (rid, sku)).fetchone()
    if decision == 'commit' and hold is None:
        return
    if hold is not None:
        if hold['qty'] != qty:
            return
        if hold['state'] == 'committed' and decision == 'abort':
            return
        if hold['state'] == 'released' and decision == 'commit':
            return
    if part is None:
        conn.execute('INSERT INTO bridge_parts(rid,sku,qty,fp,decision) VALUES(?,?,?,?,?)', (rid, sku, qty, fp, decision))
    else:
        conn.execute('UPDATE bridge_parts SET decision=? WHERE rid=? AND sku=?', (decision, rid, sku))
    if hold is not None and hold['state'] == 'prepared':
        state = 'committed' if decision == 'commit' else 'released'
        conn.execute('UPDATE legacy_holds SET state=? WHERE reservation_id=? AND sku=?', (state, rid, sku))
        if decision == 'abort':
            conn.execute('UPDATE legacy_stock SET available=available+? WHERE sku=?', (qty, sku))
    _send(out, 'gateway', 'finished', rid=rid, sku=sku, fp=fp, decision=decision)


def _legacy_run(conn, body, out):
    rid, fp = body['rid'], body['fp']
    old = conn.execute('SELECT * FROM legacy_requests WHERE reservation_id=?', (rid,)).fetchone()
    if old is not None:
        status = old['status'] if old['fingerprint'] == fp else 'idempotency_conflict'
        _send(out, 'gateway', 'legacy_result', rid=rid, fp=fp, status=status)
        return
    routed = conn.execute('SELECT fp FROM bridge_routed WHERE rid=?', (rid,)).fetchone()
    if routed is not None:
        if routed['fp'] == fp:
            _send(out, 'gateway', 'legacy_result', rid=rid, fp=fp, status='route')
        return
    lines = json.loads(fp)
    stocks = [conn.execute('SELECT active FROM legacy_stock WHERE sku=?', (sku,)).fetchone() for sku in lines]
    if any(stock is None or not stock['active'] for stock in stocks):
        conn.execute('INSERT INTO bridge_routed(rid,fp) VALUES(?,?)', (rid, fp))
        _send(out, 'gateway', 'legacy_result', rid=rid, fp=fp, status='route')
        return
    for sku in lines:
        if conn.execute("SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared' LIMIT 1", (sku,)).fetchone() is not None:
            _send(out, 'gateway', 'legacy_result', rid=rid, fp=fp, status='wait')
            return
    result = legacy.reserve(conn, rid, lines)
    _send(out, 'gateway', 'legacy_result', rid=rid, fp=fp, status=result['status'])


def _advance_moves(conn):
    changed = False
    moves = conn.execute("SELECT * FROM bridge_moves WHERE state='waiting' ORDER BY sku").fetchall()
    for move in moves:
        sku = move['sku']
        stock = conn.execute('SELECT * FROM legacy_stock WHERE sku=?', (sku,)).fetchone()
        if stock is None or not stock['active']:
            continue
        if conn.execute("SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared' LIMIT 1", (sku,)).fetchone() is not None:
            continue
        holds = []
        rows = conn.execute("SELECT reservation_id,qty FROM legacy_holds WHERE sku=? AND state='committed' ORDER BY reservation_id", (sku,)).fetchall()
        for hold in rows:
            rid = hold['reservation_id']
            receipt = conn.execute('SELECT fingerprint FROM legacy_requests WHERE reservation_id=?', (rid,)).fetchone()
            if receipt is not None:
                fp = receipt['fingerprint']
            else:
                fp = conn.execute('SELECT fp FROM bridge_parts WHERE rid=? AND sku=?', (rid, sku)).fetchone()['fp']
            holds.append({'rid': rid, 'qty': hold['qty'], 'fp': fp})
        payload = {
            'op': 'install', 'sku': sku, 'destination': move['destination'],
            'total': stock['total'], 'available': stock['available'],
            'source_epoch': stock['epoch'], 'epoch': stock['epoch'] + 1,
            'holds': holds
        }
        conn.execute('UPDATE legacy_stock SET active=0 WHERE sku=?', (sku,))
        conn.execute("UPDATE bridge_moves SET state='sent',payload=? WHERE sku=?", (_dump(payload), sku))
        changed = True
    return changed


def _emit_transfers(conn, out):
    for move in conn.execute("SELECT destination,payload FROM bridge_moves WHERE state='sent' ORDER BY sku").fetchall():
        out.append({'to': move['destination'], 'body': json.loads(move['payload'])})


def _emit_calls(conn, out):
    for call in conn.execute('SELECT * FROM bridge_calls WHERE acked=0 ORDER BY call_id').fetchall():
        _send(out, 'gateway', 'submit', call_id=call['call_id'], rid=call['rid'], lines=json.loads(call['fp']))


def on_message(conn, message):
    conn.row_factory = sqlite3.Row
    _setup(conn)
    out = []
    body, sender = message['body'], message['src']
    drive = False
    if sender == 'driver':
        kind = body.get('kind')
        if kind in ('init', 'tick'):
            drive = True
        elif kind == 'client':
            conn.execute('INSERT OR IGNORE INTO bridge_calls(call_id,rid,fp,acked) VALUES(?,?,?,0)', (body['call_id'], body['reservation_id'], _dump(body['lines'])))
            drive = True
        elif kind == 'reply_ack':
            conn.execute('UPDATE bridge_calls SET acked=1 WHERE call_id=?', (body['call_id'],))
        elif kind == 'move':
            sku, destination = body['sku'], body['destination']
            stock = conn.execute('SELECT active FROM legacy_stock WHERE sku=?', (sku,)).fetchone()
            if destination in ('A', 'B') and stock is not None and stock['active']:
                conn.execute("INSERT OR IGNORE INTO bridge_moves(sku,destination,state,payload) VALUES(?,?,'waiting',NULL)", (sku, destination))
            drive = True
    elif sender == 'gateway':
        op = body.get('op')
        if op == 'prepare':
            _prepare(conn, body, out)
        elif op == 'finish':
            _finish(conn, body, out)
        elif op == 'legacy_run':
            _legacy_run(conn, body, out)
        elif op == 'call_done':
            conn.execute('UPDATE bridge_calls SET acked=1 WHERE call_id=?', (body['call_id'],))
    elif sender in ('A', 'B') and body.get('op') == 'installed':
        move = conn.execute('SELECT * FROM bridge_moves WHERE sku=?', (body['sku'],)).fetchone()
        if move is not None and move['destination'] == sender and move['payload'] is not None:
            if json.loads(move['payload'])['epoch'] == body['epoch']:
                conn.execute("UPDATE bridge_moves SET state='done' WHERE sku=?", (body['sku'],))
    fenced = _advance_moves(conn)
    if drive:
        _emit_calls(conn, out)
    if drive or fenced:
        _emit_transfers(conn, out)
    return {'messages': out, 'replies': []}

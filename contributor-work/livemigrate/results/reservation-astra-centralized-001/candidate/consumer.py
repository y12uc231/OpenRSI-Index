import sqlite3


def _send(out, to, op, **fields):
    body = {'op': op}
    body.update(fields)
    out.append({'to': to, 'body': body})


def _setup(conn):
    statements = [
        'CREATE TABLE IF NOT EXISTS owner_meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS owner_inventory(sku TEXT PRIMARY KEY,total INTEGER NOT NULL,available INTEGER NOT NULL,epoch INTEGER NOT NULL,authority TEXT NOT NULL,route_acked INTEGER NOT NULL DEFAULT 0)',
        'CREATE TABLE IF NOT EXISTS owner_holds(rid TEXT NOT NULL,sku TEXT NOT NULL,qty INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(rid,sku))',
        "CREATE TABLE IF NOT EXISTS owner_parts(rid TEXT NOT NULL,sku TEXT NOT NULL,qty INTEGER NOT NULL,fp TEXT NOT NULL,decision TEXT NOT NULL DEFAULT '',PRIMARY KEY(rid,sku))",
        'CREATE VIEW IF NOT EXISTS audit_inventory AS SELECT sku,total,available,epoch,authority FROM owner_inventory',
        'CREATE VIEW IF NOT EXISTS audit_holds AS SELECT rid AS reservation_id,sku,qty,state FROM owner_holds'
    ]
    for statement in statements:
        conn.execute(statement)


def _vote(out, body, vote):
    _send(out, 'gateway', 'vote', rid=body['rid'], sku=body['sku'], fp=body['fp'], vote=vote)


def _prepare(conn, body, out):
    rid, sku, qty, fp = body['rid'], body['sku'], body['qty'], body['fp']
    part = conn.execute('SELECT * FROM owner_parts WHERE rid=? AND sku=?', (rid, sku)).fetchone()
    if part is not None and (part['fp'] != fp or part['qty'] != qty):
        return
    if part is not None and part['decision'] == 'abort':
        _vote(out, body, 'no')
        return
    hold = conn.execute('SELECT * FROM owner_holds WHERE rid=? AND sku=?', (rid, sku)).fetchone()
    if hold is not None:
        if hold['qty'] != qty:
            return
        _vote(out, body, 'yes' if hold['state'] in ('prepared', 'committed') else 'no')
        return
    if part is not None and part['decision'] == 'commit':
        _vote(out, body, 'wait')
        return
    stock = conn.execute('SELECT * FROM owner_inventory WHERE sku=?', (sku,)).fetchone()
    if stock is None or stock['authority'] != 'active':
        _vote(out, body, 'wait')
        return
    tentative = conn.execute("SELECT COALESCE(SUM(qty),0) FROM owner_holds WHERE sku=? AND state='prepared'", (sku,)).fetchone()[0]
    if stock['available'] + tentative < qty:
        _vote(out, body, 'no')
        return
    if stock['available'] < qty:
        _vote(out, body, 'wait')
        return
    conn.execute("INSERT OR IGNORE INTO owner_parts(rid,sku,qty,fp,decision) VALUES(?,?,?,?,'')", (rid, sku, qty, fp))
    conn.execute('UPDATE owner_inventory SET available=available-? WHERE sku=?', (qty, sku))
    conn.execute("INSERT INTO owner_holds(rid,sku,qty,state) VALUES(?,?,?,'prepared')", (rid, sku, qty))
    _vote(out, body, 'yes')


def _finish(conn, body, out):
    rid, sku, qty, fp = body['rid'], body['sku'], body['qty'], body['fp']
    decision = body['decision']
    if decision not in ('commit', 'abort'):
        return
    part = conn.execute('SELECT * FROM owner_parts WHERE rid=? AND sku=?', (rid, sku)).fetchone()
    if part is not None:
        if part['fp'] != fp or part['qty'] != qty:
            return
        if part['decision'] and part['decision'] != decision:
            return
    hold = conn.execute('SELECT * FROM owner_holds WHERE rid=? AND sku=?', (rid, sku)).fetchone()
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
        conn.execute('INSERT INTO owner_parts(rid,sku,qty,fp,decision) VALUES(?,?,?,?,?)', (rid, sku, qty, fp, decision))
    else:
        conn.execute('UPDATE owner_parts SET decision=? WHERE rid=? AND sku=?', (decision, rid, sku))
    if hold is not None and hold['state'] == 'prepared':
        state = 'committed' if decision == 'commit' else 'released'
        conn.execute('UPDATE owner_holds SET state=? WHERE rid=? AND sku=?', (state, rid, sku))
        if decision == 'abort':
            conn.execute('UPDATE owner_inventory SET available=available+? WHERE sku=?', (qty, sku))
    _send(out, 'gateway', 'finished', rid=rid, sku=sku, fp=fp, decision=decision)


def _install(conn, body, out):
    node = conn.execute("SELECT v FROM owner_meta WHERE k='node'").fetchone()
    if node is None or body['destination'] != node['v']:
        return False
    if body['epoch'] <= body['source_epoch']:
        return False
    sku = body['sku']
    stock = conn.execute('SELECT * FROM owner_inventory WHERE sku=?', (sku,)).fetchone()
    if stock is None:
        conn.execute("INSERT INTO owner_inventory(sku,total,available,epoch,authority,route_acked) VALUES(?,?,?,?,'active',0)", (sku, body['total'], body['available'], body['epoch']))
        for hold in body['holds']:
            conn.execute("INSERT INTO owner_holds(rid,sku,qty,state) VALUES(?,?,?,'committed')", (hold['rid'], sku, hold['qty']))
            conn.execute("INSERT OR IGNORE INTO owner_parts(rid,sku,qty,fp,decision) VALUES(?,?,?,?,'commit')", (hold['rid'], sku, hold['qty'], hold['fp']))
        epoch = body['epoch']
    else:
        epoch = stock['epoch']
    _send(out, 'source', 'installed', sku=sku, epoch=epoch)
    return True


def _emit_routes(conn, out):
    stocks = conn.execute("SELECT sku,epoch FROM owner_inventory WHERE authority='active' AND route_acked=0 ORDER BY sku").fetchall()
    for stock in stocks:
        _send(out, 'gateway', 'route', sku=stock['sku'], epoch=stock['epoch'])


def on_message(conn, message):
    conn.row_factory = sqlite3.Row
    _setup(conn)
    out = []
    body, sender = message['body'], message['src']
    advertise = False
    if sender == 'driver':
        if body.get('kind') == 'init':
            conn.execute("INSERT OR IGNORE INTO owner_meta(k,v) VALUES('node',?)", (body['node_id'],))
            advertise = True
        elif body.get('kind') == 'tick':
            advertise = True
    elif sender == 'source' and body.get('op') == 'install':
        advertise = _install(conn, body, out)
    elif sender == 'gateway':
        op = body.get('op')
        if op == 'prepare':
            _prepare(conn, body, out)
        elif op == 'finish':
            _finish(conn, body, out)
        elif op == 'route_ack':
            conn.execute('UPDATE owner_inventory SET route_acked=1 WHERE sku=? AND epoch=?', (body['sku'], body['epoch']))
    if advertise:
        _emit_routes(conn, out)
    return {'messages': out, 'replies': []}

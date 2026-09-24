import json
import sqlite3


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _send(out, to, op, **fields):
    body = {'op': op}
    body.update(fields)
    out.append({'to': to, 'body': body})


def _setup(conn):
    statements = [
        'CREATE TABLE IF NOT EXISTS gw_requests(rid TEXT PRIMARY KEY,fp TEXT NOT NULL,mode TEXT NOT NULL,state TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS gw_calls(call_id TEXT PRIMARY KEY,rid TEXT NOT NULL,fp TEXT NOT NULL,origin TEXT NOT NULL,acked INTEGER NOT NULL DEFAULT 0)',
        'CREATE TABLE IF NOT EXISTS gw_routes(sku TEXT PRIMARY KEY,node TEXT NOT NULL,epoch INTEGER NOT NULL)',
        'CREATE TABLE IF NOT EXISTS gw_parts(rid TEXT NOT NULL,sku TEXT NOT NULL,qty INTEGER NOT NULL,node TEXT NOT NULL,phase TEXT NOT NULL,PRIMARY KEY(rid,sku))',
        'CREATE TABLE IF NOT EXISTS gw_attempts(rid TEXT NOT NULL,sku TEXT NOT NULL,node TEXT NOT NULL,acked INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(rid,sku,node))',
        "CREATE VIEW IF NOT EXISTS audit_decisions AS SELECT rid AS reservation_id,fp AS lines_json,state FROM gw_requests WHERE state IN ('commit','abort')"
    ]
    for statement in statements:
        conn.execute(statement)


def _has_moved_line(conn, lines):
    for sku in lines:
        route = conn.execute('SELECT node FROM gw_routes WHERE sku=?', (sku,)).fetchone()
        if route is not None and route['node'] != 'source':
            return True
    return False


def _make_parts(conn, rid, fp):
    for sku, qty in sorted(json.loads(fp).items()):
        route = conn.execute('SELECT node FROM gw_routes WHERE sku=?', (sku,)).fetchone()
        node = route['node'] if route is not None else 'source'
        conn.execute("INSERT OR IGNORE INTO gw_parts(rid,sku,qty,node,phase) VALUES(?,?,?,?,'waiting')", (rid, sku, qty, node))


def _admit(conn, call_id, rid, lines, origin):
    fp = _dump(lines)
    old = conn.execute('SELECT rid FROM gw_requests WHERE rid=?', (rid,)).fetchone()
    if old is None:
        mode = 'distributed'
        if origin == 'source' and not _has_moved_line(conn, lines):
            mode = 'legacy'
        conn.execute("INSERT INTO gw_requests(rid,fp,mode,state) VALUES(?,?,?,'pending')", (rid, fp, mode))
        if mode == 'distributed':
            _make_parts(conn, rid, fp)
    conn.execute('INSERT OR IGNORE INTO gw_calls(call_id,rid,fp,origin,acked) VALUES(?,?,?,?,0)', (call_id, rid, fp, origin))


def _route(conn, sku, node, epoch):
    old = conn.execute('SELECT * FROM gw_routes WHERE sku=?', (sku,)).fetchone()
    if old is None:
        conn.execute('INSERT INTO gw_routes(sku,node,epoch) VALUES(?,?,?)', (sku, node, epoch))
        return True
    if epoch > old['epoch']:
        conn.execute('UPDATE gw_routes SET node=?,epoch=? WHERE sku=?', (node, epoch, sku))
        return True
    return False


def _drive(conn, out):
    requests = conn.execute("SELECT * FROM gw_requests WHERE state='pending' ORDER BY rid").fetchall()
    for request in requests:
        rid, fp = request['rid'], request['fp']
        if request['mode'] == 'legacy':
            if not _has_moved_line(conn, json.loads(fp)):
                _send(out, 'source', 'legacy_run', rid=rid, fp=fp)
                continue
            # A learned handoff proves that a requested source SKU is fenced.
            # Earlier commits survive at the participants under this identity.
            # Earlier shortages remain permanent because commits never cancel.
            conn.execute("UPDATE gw_requests SET mode='distributed' WHERE rid=?", (rid,))
            _make_parts(conn, rid, fp)
        part = conn.execute("SELECT * FROM gw_parts WHERE rid=? AND phase='waiting' ORDER BY sku LIMIT 1", (rid,)).fetchone()
        if part is None:
            conn.execute("UPDATE gw_requests SET state='commit' WHERE rid=? AND state='pending'", (rid,))
            continue
        route = conn.execute('SELECT node FROM gw_routes WHERE sku=?', (part['sku'],)).fetchone()
        node = route['node'] if route is not None else part['node']
        if node != part['node']:
            conn.execute('UPDATE gw_parts SET node=? WHERE rid=? AND sku=?', (node, rid, part['sku']))
        conn.execute('INSERT OR IGNORE INTO gw_attempts(rid,sku,node,acked) VALUES(?,?,?,0)', (rid, part['sku'], node))
        _send(out, node, 'prepare', rid=rid, sku=part['sku'], qty=part['qty'], fp=fp)
    attempts = conn.execute("SELECT a.rid,a.sku,a.node,r.fp,r.state,p.qty FROM gw_attempts AS a JOIN gw_requests AS r ON r.rid=a.rid JOIN gw_parts AS p ON p.rid=a.rid AND p.sku=a.sku WHERE a.acked=0 AND (r.state='abort' OR (r.state='commit' AND a.node=p.node AND p.phase='yes')) ORDER BY a.rid,a.sku,a.node").fetchall()
    for attempt in attempts:
        _send(out, attempt['node'], 'finish', rid=attempt['rid'], sku=attempt['sku'], qty=attempt['qty'], fp=attempt['fp'], decision=attempt['state'])


def _replies(conn):
    replies = []
    calls = conn.execute('SELECT c.call_id,c.rid,c.fp,r.fp AS accepted_fp,r.state FROM gw_calls AS c JOIN gw_requests AS r ON r.rid=c.rid WHERE c.acked=0 ORDER BY c.call_id').fetchall()
    for call in calls:
        if call['state'] not in ('commit', 'abort'):
            continue
        if call['fp'] != call['accepted_fp']:
            status = 'idempotency_conflict'
        elif call['state'] == 'commit':
            status = 'committed'
        else:
            status = 'out_of_stock'
        replies.append({'call_id': call['call_id'], 'reservation_id': call['rid'], 'status': status, 'lines': json.loads(call['fp'])})
    return replies


def on_message(conn, message):
    conn.row_factory = sqlite3.Row
    _setup(conn)
    out = []
    body, sender = message['body'], message['src']
    drive = False
    if sender == 'driver':
        kind = body.get('kind')
        if kind == 'init':
            for sku, node in body['routing'].items():
                conn.execute('INSERT OR IGNORE INTO gw_routes(sku,node,epoch) VALUES(?,?,0)', (sku, node))
            drive = True
        elif kind == 'tick':
            drive = True
        elif kind == 'client':
            _admit(conn, body['call_id'], body['reservation_id'], body['lines'], 'gateway')
            drive = True
        elif kind == 'reply_ack':
            call = conn.execute('SELECT origin FROM gw_calls WHERE call_id=?', (body['call_id'],)).fetchone()
            conn.execute('UPDATE gw_calls SET acked=1 WHERE call_id=?', (body['call_id'],))
            if call is not None and call['origin'] == 'source':
                _send(out, 'source', 'call_done', call_id=body['call_id'])
    else:
        op = body.get('op')
        if sender == 'source' and op == 'submit':
            _admit(conn, body['call_id'], body['rid'], body['lines'], 'source')
            call = conn.execute('SELECT acked FROM gw_calls WHERE call_id=?', (body['call_id'],)).fetchone()
            if call['acked']:
                _send(out, 'source', 'call_done', call_id=body['call_id'])
            drive = True
        elif sender == 'source' and op == 'legacy_result':
            request = conn.execute('SELECT * FROM gw_requests WHERE rid=?', (body['rid'],)).fetchone()
            if request is not None and request['fp'] == body['fp'] and request['state'] == 'pending':
                status = body['status']
                if status in ('committed', 'out_of_stock'):
                    # A matching durable legacy receipt remains authoritative
                    # after conversion to distributed processing.
                    state = 'commit' if status == 'committed' else 'abort'
                    conn.execute('UPDATE gw_requests SET state=? WHERE rid=?', (state, body['rid']))
                    drive = True
                elif status == 'route' and request['mode'] == 'legacy':
                    conn.execute("UPDATE gw_requests SET mode='distributed' WHERE rid=?", (body['rid'],))
                    _make_parts(conn, body['rid'], body['fp'])
                    drive = True
        elif sender in ('source', 'A', 'B') and op == 'vote':
            request = conn.execute('SELECT * FROM gw_requests WHERE rid=?', (body['rid'],)).fetchone()
            part = conn.execute('SELECT * FROM gw_parts WHERE rid=? AND sku=?', (body['rid'], body['sku'])).fetchone()
            if request is not None and part is not None and request['state'] == 'pending' and request['mode'] == 'distributed' and request['fp'] == body['fp'] and part['node'] == sender and part['phase'] == 'waiting':
                vote = body['vote']
                if vote == 'yes':
                    conn.execute("UPDATE gw_parts SET phase='yes' WHERE rid=? AND sku=?", (body['rid'], body['sku']))
                    drive = True
                elif vote == 'no':
                    conn.execute("UPDATE gw_requests SET state='abort' WHERE rid=?", (body['rid'],))
                    drive = True
                elif vote == 'redirect' and sender == 'source' and body.get('destination') in ('A', 'B'):
                    _route(conn, body['sku'], body['destination'], body['epoch'])
                    drive = True
        elif sender in ('source', 'A', 'B') and op == 'finished':
            request = conn.execute('SELECT fp,state FROM gw_requests WHERE rid=?', (body['rid'],)).fetchone()
            if request is not None and request['state'] in ('commit', 'abort') and request['state'] == body['decision'] and request['fp'] == body['fp']:
                conn.execute('UPDATE gw_attempts SET acked=1 WHERE rid=? AND sku=? AND node=?', (body['rid'], body['sku'], sender))
        elif sender in ('A', 'B') and op == 'route':
            changed = _route(conn, body['sku'], sender, body['epoch'])
            _send(out, sender, 'route_ack', sku=body['sku'], epoch=body['epoch'])
            drive = changed
    if drive:
        _drive(conn, out)
    return {'messages': out, 'replies': _replies(conn)}

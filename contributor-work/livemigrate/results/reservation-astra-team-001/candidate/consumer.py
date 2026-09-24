import json


_MAX_SQL_INT = 9223372036854775807


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _schema(conn):
    statements = [
        "CREATE TABLE IF NOT EXISTS consumer_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),node_id TEXT NOT NULL,capacities_json TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS consumer_inventory(sku TEXT PRIMARY KEY,total INTEGER NOT NULL,available INTEGER NOT NULL,epoch INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS consumer_requests(reservation_id TEXT PRIMARY KEY,lines_json TEXT NOT NULL,state TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS consumer_holds(reservation_id TEXT NOT NULL,sku TEXT NOT NULL,qty INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(reservation_id,sku))",
        "CREATE VIEW IF NOT EXISTS audit_inventory AS SELECT sku,total,available,epoch,'active' AS authority FROM consumer_inventory",
        "CREATE VIEW IF NOT EXISTS audit_holds AS SELECT reservation_id,sku,qty,state FROM consumer_holds",
    ]
    for statement in statements:
        conn.execute(statement)


def _initialize(conn, body):
    node_id = body.get("node_id")
    capacities = body.get("capacities")
    if node_id not in ("A", "B") or not isinstance(capacities, dict):
        return False
    for sku, total in capacities.items():
        if not isinstance(sku, str) or not sku:
            return False
        if type(total) is not int or not 0 <= total <= _MAX_SQL_INT:
            return False
    encoded = _json(capacities)
    old = conn.execute(
        "SELECT node_id,capacities_json FROM consumer_meta WHERE singleton=1"
    ).fetchone()
    if old is not None:
        return old[0] == node_id and old[1] == encoded
    conn.execute(
        "INSERT INTO consumer_meta(singleton,node_id,capacities_json) VALUES(1,?,?)",
        (node_id, encoded),
    )
    return True


def _configuration(conn):
    row = conn.execute(
        "SELECT node_id,capacities_json FROM consumer_meta WHERE singleton=1"
    ).fetchone()
    if row is None:
        return None
    return row[0], json.loads(row[1])


def _valid(capacities, reservation_id, lines):
    if not isinstance(reservation_id, str) or not reservation_id:
        return False
    if not isinstance(lines, dict) or not lines:
        return False
    for sku, qty in lines.items():
        if not isinstance(sku, str) or sku not in capacities:
            return False
        if type(qty) is not int or qty <= 0:
            return False
    return True


def _valid_epoch(epoch):
    return type(epoch) is int and 0 <= epoch <= _MAX_SQL_INT


def _stock(conn, sku):
    return conn.execute(
        "SELECT total,available,epoch FROM consumer_inventory WHERE sku=?",
        (sku,),
    ).fetchone()


def _remember(conn, reservation_id, lines):
    encoded = _json(lines)
    old = conn.execute(
        "SELECT lines_json,state FROM consumer_requests WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()
    if old is not None:
        return old[1] if old[0] == encoded else None
    conn.execute(
        "INSERT INTO consumer_requests VALUES(?,?,'pending')",
        (reservation_id, encoded),
    )
    return "pending"


def _send(out, destination, body):
    out["messages"].append({"to": destination, "body": body})


def _route(out, node_id, sku, epoch):
    _send(out, "gateway", {
        "kind": "route",
        "sku": sku,
        "owner": node_id,
        "epoch": epoch,
    })


def _installed(out, sku, epoch):
    _send(out, "source", {
        "kind": "installed",
        "sku": sku,
        "epoch": epoch,
    })


def _vote(out, body, vote, epoch, owner=None):
    answer = {
        "kind": "vote",
        "reservation_id": body["reservation_id"],
        "lines": body["lines"],
        "sku": body["sku"],
        "epoch": epoch,
        "vote": vote,
    }
    if owner is not None:
        answer["owner"] = owner
    _send(out, "gateway", answer)


def _redirect(out, node_id, body, epoch):
    _route(out, node_id, body["sku"], epoch)
    _vote(out, body, "redirect", epoch, node_id)


def _ack(out, body, decision, epoch):
    _send(out, "gateway", {
        "kind": "decision_ack",
        "reservation_id": body["reservation_id"],
        "lines": body["lines"],
        "sku": body["sku"],
        "epoch": epoch,
        "decision": decision,
    })


def _announce(conn, out, node_id):
    for sku, epoch in conn.execute(
        "SELECT sku,epoch FROM consumer_inventory ORDER BY sku"
    ).fetchall():
        _route(out, node_id, sku, epoch)


def _finish_commit(conn, reservation_id):
    conn.execute(
        "UPDATE consumer_requests SET state='commit' WHERE reservation_id=?",
        (reservation_id,),
    )
    conn.execute(
        "UPDATE consumer_holds SET state='committed' WHERE reservation_id=? AND state='prepared'",
        (reservation_id,),
    )


def _install(conn, out, node_id, capacities, body):
    sku = body.get("sku")
    epoch = body.get("epoch")
    previous_epoch = body.get("previous_epoch")
    total = body.get("total")
    available = body.get("available")
    if not isinstance(sku, str) or sku not in capacities:
        return
    if not _valid_epoch(epoch) or not _valid_epoch(previous_epoch):
        return
    if epoch <= previous_epoch:
        return
    if type(total) is not int or total != capacities[sku]:
        return
    if type(available) is not int or not 0 <= available <= total:
        return

    existing = _stock(conn, sku)
    if existing is not None:
        # Installation is a one-time source-to-owner transfer. Even an exact
        # replay must never restore its old availability or replace holds.
        if existing[2] == epoch:
            _installed(out, sku, epoch)
        _route(out, node_id, sku, existing[2])
        return

    raw_holds = body.get("holds")
    if not isinstance(raw_holds, list):
        return
    if conn.execute(
        "SELECT 1 FROM consumer_holds WHERE sku=? LIMIT 1", (sku,)
    ).fetchone() is not None:
        return

    # Validate the complete transfer before changing any inventory. Source
    # certifies that it is fenced and has drained all tentative holds.
    normalized = []
    identities = set()
    used = 0
    for item in raw_holds:
        if not isinstance(item, dict):
            return
        reservation_id = item.get("reservation_id")
        lines = item.get("lines")
        qty = item.get("qty")
        if not _valid(capacities, reservation_id, lines):
            return
        if reservation_id in identities or item.get("state") != "committed":
            return
        if type(qty) is not int or qty <= 0:
            return
        if sku not in lines or qty != lines[sku]:
            return
        encoded = _json(lines)
        old = conn.execute(
            "SELECT lines_json,state FROM consumer_requests WHERE reservation_id=?",
            (reservation_id,),
        ).fetchone()
        if old is not None:
            if old[0] != encoded or old[1] not in ("pending", "commit"):
                return
        identities.add(reservation_id)
        used += qty
        if used > total:
            return
        normalized.append((reservation_id, qty, encoded))
    if available + used != total:
        return

    conn.execute(
        "INSERT INTO consumer_inventory(sku,total,available,epoch) VALUES(?,?,?,?)",
        (sku, total, available, epoch),
    )
    for reservation_id, qty, encoded in normalized:
        conn.execute(
            "INSERT OR IGNORE INTO consumer_requests VALUES(?,?,'commit')",
            (reservation_id, encoded),
        )
        conn.execute(
            "INSERT INTO consumer_holds VALUES(?,?,?,'committed')",
            (reservation_id, sku, qty),
        )
        # A copied commitment comes from either the atomic legacy bundle or
        # the irrevocable global decision, under the same complete identity.
        _finish_commit(conn, reservation_id)
    _installed(out, sku, epoch)
    _route(out, node_id, sku, epoch)


def _prepare(conn, out, node_id, capacities, body):
    reservation_id = body.get("reservation_id")
    lines = body.get("lines")
    sku = body.get("sku")
    epoch = body.get("epoch")
    if not _valid(capacities, reservation_id, lines):
        return
    if not isinstance(sku, str) or sku not in lines or not _valid_epoch(epoch):
        return
    qty = lines[sku]
    if "qty" in body and (type(body["qty"]) is not int or body["qty"] != qty):
        return

    state = _remember(conn, reservation_id, lines)
    stock = _stock(conn, sku)
    answer_epoch = epoch if stock is None else stock[2]
    if state is None:
        _vote(out, body, "conflict", answer_epoch)
        return
    if stock is None:
        # Routing may precede delivery of the installation certificate.
        _vote(out, body, "wait", epoch)
        return
    if epoch != stock[2]:
        _redirect(out, node_id, body, stock[2])
        return
    if state in ("abort", "reject"):
        _vote(out, body, "no", stock[2])
        return

    hold = conn.execute(
        "SELECT qty,state FROM consumer_holds WHERE reservation_id=? AND sku=?",
        (reservation_id, sku),
    ).fetchone()
    if hold is not None:
        if hold[0] != qty:
            _vote(out, body, "conflict", stock[2])
        else:
            _vote(out, body, "yes" if hold[1] in ("prepared", "committed") else "no", stock[2])
        return
    if state == "commit":
        # A delayed transfer must supply its historical committed hold;
        # a decision alone must never manufacture a second allocation.
        _vote(out, body, "wait", stock[2])
        return

    if stock[1] < qty:
        committed_qty = conn.execute(
            "SELECT COALESCE(SUM(qty),0) FROM consumer_holds WHERE sku=? AND state='committed'",
            (sku,),
        ).fetchone()[0]
        if stock[0] - committed_qty < qty:
            conn.execute(
                "UPDATE consumer_requests SET state='reject' WHERE reservation_id=? AND state='pending'",
                (reservation_id,),
            )
            _vote(out, body, "no", stock[2])
        else:
            # Abortable reservations cannot justify a permanent rejection.
            _vote(out, body, "wait", stock[2])
        return

    conn.execute(
        "UPDATE consumer_inventory SET available=available-? WHERE sku=?",
        (qty, sku),
    )
    conn.execute(
        "INSERT INTO consumer_holds VALUES(?,?,?,'prepared')",
        (reservation_id, sku, qty),
    )
    _vote(out, body, "yes", stock[2])


def _decision(conn, out, node_id, capacities, body):
    reservation_id = body.get("reservation_id")
    lines = body.get("lines")
    sku = body.get("sku")
    epoch = body.get("epoch")
    decision = body.get("decision")
    if decision not in ("commit", "abort"):
        return
    if not _valid(capacities, reservation_id, lines):
        return
    if not isinstance(sku, str) or sku not in lines or not _valid_epoch(epoch):
        return
    state = _remember(conn, reservation_id, lines)
    if state is None:
        return

    if decision == "abort":
        has_committed = conn.execute(
            "SELECT 1 FROM consumer_holds WHERE reservation_id=? AND state='committed' LIMIT 1",
            (reservation_id,),
        ).fetchone() is not None
        if state == "commit" or has_committed:
            return
        prepared = conn.execute(
            "SELECT sku,qty FROM consumer_holds WHERE reservation_id=? AND state='prepared'",
            (reservation_id,),
        ).fetchall()
        for held_sku, qty in prepared:
            conn.execute(
                "UPDATE consumer_inventory SET available=available+? WHERE sku=?",
                (qty, held_sku),
            )
        conn.execute(
            "UPDATE consumer_holds SET state='released' WHERE reservation_id=? AND state='prepared'",
            (reservation_id,),
        )
        conn.execute(
            "UPDATE consumer_requests SET state='abort' WHERE reservation_id=?",
            (reservation_id,),
        )
        # The full-identity tombstone also covers a prepare or installation
        # that has not arrived. Echo the contacted epoch for its cleanup ACK.
        _ack(out, body, "abort", epoch)
        return

    if state in ("abort", "reject"):
        return
    # Persist even a reordered commit received before its transfer. Finish
    # existing local work, but acknowledge only an actually committed line.
    _finish_commit(conn, reservation_id)
    stock = _stock(conn, sku)
    hold = conn.execute(
        "SELECT qty,state FROM consumer_holds WHERE reservation_id=? AND sku=?",
        (reservation_id, sku),
    ).fetchone()
    if stock is None:
        return
    if epoch != stock[2]:
        _redirect(out, node_id, body, stock[2])
        return
    if hold is not None and hold[0] == lines[sku] and hold[1] == "committed":
        _ack(out, body, "commit", stock[2])


def on_message(conn, message):
    _schema(conn)
    out = {"messages": [], "replies": []}
    if not isinstance(message, dict):
        return out
    sender = message.get("src")
    body = message.get("body", {})
    if not isinstance(body, dict):
        return out
    kind = body.get("kind")

    if sender == "driver" and kind == "init":
        if not _initialize(conn, body):
            return out
    configuration = _configuration(conn)
    if configuration is None:
        return out
    node_id, capacities = configuration

    if sender == "driver":
        if kind in ("init", "tick"):
            _announce(conn, out, node_id)
    elif sender == "source" and kind == "install":
        _install(conn, out, node_id, capacities, body)
    elif sender == "gateway":
        if kind == "prepare":
            _prepare(conn, out, node_id, capacities, body)
        elif kind == "decision":
            _decision(conn, out, node_id, capacities, body)
    return out

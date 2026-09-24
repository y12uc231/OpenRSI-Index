import json
import legacy


_MAX_SQL_INT = 9223372036854775807


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _schema(conn):
    statements = [
        "CREATE TABLE IF NOT EXISTS bridge_calls(call_id TEXT PRIMARY KEY,reservation_id TEXT NOT NULL,lines_json TEXT NOT NULL,acked INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS bridge_requests(reservation_id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,lines_json TEXT NOT NULL,state TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS bridge_moves(sku TEXT PRIMARY KEY,destination TEXT NOT NULL,epoch INTEGER NOT NULL,phase TEXT NOT NULL,snapshot_json TEXT,installed INTEGER NOT NULL DEFAULT 0)",
        "CREATE VIEW IF NOT EXISTS audit_inventory AS SELECT sku,total,available,epoch,CASE WHEN active=1 THEN 'active' ELSE 'fenced' END AS authority FROM legacy_stock",
        "CREATE VIEW IF NOT EXISTS audit_holds AS SELECT reservation_id,sku,qty,state FROM legacy_holds",
    ]
    for statement in statements:
        conn.execute(statement)


def _send(out, destination, body):
    out["messages"].append({"to": destination, "body": body})


def _valid_epoch(epoch):
    return type(epoch) is int and 0 <= epoch <= _MAX_SQL_INT


def _valid(conn, reservation_id, lines):
    if not isinstance(reservation_id, str) or not reservation_id:
        return False
    if not isinstance(lines, dict) or not lines:
        return False
    for sku, qty in lines.items():
        if not isinstance(sku, str) or not sku:
            return False
        if type(qty) is not int or qty <= 0:
            return False
        if conn.execute("SELECT 1 FROM legacy_stock WHERE sku=?", (sku,)).fetchone() is None:
            return False
    return True


def _remember(conn, reservation_id, lines):
    encoded = _json(lines)
    receipt = conn.execute(
        "SELECT fingerprint,status FROM legacy_requests WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()
    if receipt is not None and receipt[0] != encoded:
        return False
    row = conn.execute(
        "SELECT fingerprint FROM bridge_requests WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()
    if row is not None:
        return row[0] == encoded
    state = "pending"
    if receipt is not None:
        state = "commit" if receipt[1] == "committed" else "reject"
    conn.execute(
        "INSERT INTO bridge_requests VALUES(?,?,?,?)",
        (reservation_id, encoded, encoded, state),
    )
    return True


def _stock(conn, sku):
    return conn.execute(
        "SELECT total,available,epoch,active FROM legacy_stock WHERE sku=?",
        (sku,),
    ).fetchone()


def _route(conn, sku):
    stock = _stock(conn, sku)
    if stock is None:
        return None
    if stock[3]:
        return {"kind": "route", "sku": sku, "owner": "source", "epoch": stock[2]}
    move = conn.execute(
        "SELECT destination,epoch FROM bridge_moves WHERE sku=? AND phase='fenced'",
        (sku,),
    ).fetchone()
    if move is None:
        return None
    return {"kind": "route", "sku": sku, "owner": move[0], "epoch": move[1]}


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


def _redirect(conn, out, body):
    route = _route(conn, body["sku"])
    if route is not None:
        _send(out, "gateway", route)
        _vote(out, body, "redirect", route["epoch"], route["owner"])


def _prepare(conn, out, body):
    reservation_id = body.get("reservation_id")
    lines = body.get("lines")
    sku = body.get("sku")
    epoch = body.get("epoch")
    if not _valid(conn, reservation_id, lines):
        return
    if not isinstance(sku, str) or sku not in lines or not _valid_epoch(epoch):
        return
    qty = lines[sku]
    if "qty" in body and (type(body["qty"]) is not int or body["qty"] != qty):
        return
    stock = _stock(conn, sku)
    if not _remember(conn, reservation_id, lines):
        _vote(out, body, "conflict", stock[2])
        return
    if not stock[3] or epoch != stock[2]:
        _redirect(conn, out, body)
        return
    state = conn.execute(
        "SELECT state FROM bridge_requests WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()[0]
    if state in ("abort", "reject"):
        _vote(out, body, "no", stock[2])
        return
    hold = conn.execute(
        "SELECT qty,state FROM legacy_holds WHERE reservation_id=? AND sku=?",
        (reservation_id, sku),
    ).fetchone()
    if hold is not None:
        if hold[0] != qty:
            _vote(out, body, "conflict", stock[2])
        else:
            _vote(out, body, "yes" if hold[1] in ("prepared", "committed") else "no", stock[2])
        return
    if state == "commit":
        _vote(out, body, "wait", stock[2])
        return

    # Gateway admission establishes the full global identity before any work.
    # The immutable engine may commit a wholly local bundle atomically.
    all_local = all(_stock(conn, item)[3] for item in lines)
    if all_local:
        tentative = any(
            conn.execute(
                "SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared' LIMIT 1",
                (item,),
            ).fetchone() is not None
            for item in lines
        )
        if tentative:
            _vote(out, body, "wait", stock[2])
            return
        existing = conn.execute(
            "SELECT 1 FROM legacy_holds WHERE reservation_id=? LIMIT 1",
            (reservation_id,),
        ).fetchone()
        if existing is None:
            result = legacy.reserve(conn, reservation_id, lines)
            if result["status"] == "idempotency_conflict":
                _vote(out, body, "conflict", stock[2])
                return
            committed = result["status"] == "committed"
            conn.execute(
                "UPDATE bridge_requests SET state=? WHERE reservation_id=?",
                ("commit" if committed else "reject", reservation_id),
            )
            _vote(out, body, "yes" if committed else "no", stock[2])
            return

    # Tentative consumption cannot justify a permanent stock rejection.
    if stock[1] < qty:
        committed_qty = conn.execute(
            "SELECT COALESCE(SUM(qty),0) FROM legacy_holds WHERE sku=? AND state='committed'",
            (sku,),
        ).fetchone()[0]
        if stock[0] - committed_qty < qty:
            conn.execute(
                "UPDATE bridge_requests SET state='reject' WHERE reservation_id=?",
                (reservation_id,),
            )
            _vote(out, body, "no", stock[2])
        else:
            _vote(out, body, "wait", stock[2])
        return
    conn.execute(
        "UPDATE legacy_stock SET available=available-? WHERE sku=? AND active=1",
        (qty, sku),
    )
    conn.execute(
        "INSERT INTO legacy_holds(reservation_id,sku,qty,state) VALUES(?,?,?,'prepared')",
        (reservation_id, sku, qty),
    )
    _vote(out, body, "yes", stock[2])


def _ack(out, body, decision, epoch):
    _send(out, "gateway", {
        "kind": "decision_ack",
        "reservation_id": body["reservation_id"],
        "lines": body["lines"],
        "sku": body["sku"],
        "epoch": epoch,
        "decision": decision,
    })


def _decision(conn, out, body):
    reservation_id = body.get("reservation_id")
    lines = body.get("lines")
    sku = body.get("sku")
    epoch = body.get("epoch")
    decision = body.get("decision")
    if decision not in ("commit", "abort"):
        return
    if not _valid(conn, reservation_id, lines):
        return
    if not isinstance(sku, str) or sku not in lines or not _valid_epoch(epoch):
        return
    if not _remember(conn, reservation_id, lines):
        return
    stock = _stock(conn, sku)
    state = conn.execute(
        "SELECT state FROM bridge_requests WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()[0]
    receipt = conn.execute(
        "SELECT status FROM legacy_requests WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()
    has_committed = conn.execute(
        "SELECT 1 FROM legacy_holds WHERE reservation_id=? AND state='committed' LIMIT 1",
        (reservation_id,),
    ).fetchone() is not None
    encoded = _json(lines)

    if decision == "abort":
        if state == "commit" or has_committed or (receipt is not None and receipt[0] == "committed"):
            _ack(out, body, "commit", stock[2])
            return
        holds = conn.execute(
            "SELECT sku,qty FROM legacy_holds WHERE reservation_id=? AND state='prepared'",
            (reservation_id,),
        ).fetchall()
        for held_sku, qty in holds:
            conn.execute(
                "UPDATE legacy_stock SET available=available+? WHERE sku=?",
                (qty, held_sku),
            )
        conn.execute(
            "UPDATE legacy_holds SET state='released' WHERE reservation_id=? AND state='prepared'",
            (reservation_id,),
        )
        conn.execute(
            "UPDATE bridge_requests SET state='abort' WHERE reservation_id=?",
            (reservation_id,),
        )
        if receipt is None:
            conn.execute(
                "INSERT INTO legacy_requests VALUES(?,?,'out_of_stock',?)",
                (reservation_id, encoded, encoded),
            )
        _ack(out, body, "abort", stock[2])
        return

    if state in ("abort", "reject") or (receipt is not None and receipt[0] != "committed"):
        _ack(out, body, "abort", stock[2])
        return
    hold = conn.execute(
        "SELECT qty,state FROM legacy_holds WHERE reservation_id=? AND sku=?",
        (reservation_id, sku),
    ).fetchone()
    if hold is None or hold[0] != lines[sku] or hold[1] not in ("prepared", "committed"):
        if not stock[3]:
            _redirect(conn, out, body)
        return
    # An authenticated global decision covers every local line of this ID.
    conn.execute(
        "UPDATE legacy_holds SET state='committed' WHERE reservation_id=? AND state='prepared'",
        (reservation_id,),
    )
    conn.execute(
        "UPDATE bridge_requests SET state='commit' WHERE reservation_id=?",
        (reservation_id,),
    )
    if receipt is None:
        conn.execute(
            "INSERT INTO legacy_requests VALUES(?,?,'committed',?)",
            (reservation_id, encoded, encoded),
        )
    _ack(out, body, "commit", stock[2])


def _send_transfer(conn, out, sku):
    move = conn.execute(
        "SELECT destination,snapshot_json,installed FROM bridge_moves WHERE sku=? AND phase='fenced'",
        (sku,),
    ).fetchone()
    if move is None:
        return
    if not move[2]:
        _send(out, move[0], json.loads(move[1]))
    route = _route(conn, sku)
    if route is not None:
        _send(out, "gateway", route)


def _fence_ready(conn, out):
    moves = conn.execute(
        "SELECT sku,destination,epoch FROM bridge_moves WHERE phase='waiting' ORDER BY sku"
    ).fetchall()
    for sku, destination, next_epoch in moves:
        if conn.execute(
            "SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared' LIMIT 1",
            (sku,),
        ).fetchone() is not None:
            continue
        stock = _stock(conn, sku)
        if not stock[3]:
            continue
        holds = []
        for reservation_id, qty in conn.execute(
            "SELECT reservation_id,qty FROM legacy_holds WHERE sku=? AND state='committed' ORDER BY reservation_id",
            (sku,),
        ).fetchall():
            identity = conn.execute(
                "SELECT lines_json FROM legacy_requests WHERE reservation_id=?",
                (reservation_id,),
            ).fetchone()
            if identity is None:
                identity = conn.execute(
                    "SELECT lines_json FROM bridge_requests WHERE reservation_id=?",
                    (reservation_id,),
                ).fetchone()
            if identity is None:
                raise RuntimeError("Committed hold has no durable reservation identity")
            holds.append({
                "reservation_id": reservation_id,
                "qty": qty,
                "state": "committed",
                "lines": json.loads(identity[0]),
            })
        snapshot = {
            "kind": "install",
            "sku": sku,
            "total": stock[0],
            "available": stock[1],
            "previous_epoch": stock[2],
            "epoch": next_epoch,
            "holds": holds,
        }
        # Fencing and the immutable retransmission image share one transaction.
        # Historical source inventory and committed holds remain intact.
        conn.execute("UPDATE legacy_stock SET active=0 WHERE sku=?", (sku,))
        conn.execute(
            "UPDATE bridge_moves SET phase='fenced',snapshot_json=? WHERE sku=?",
            (_json(snapshot), sku),
        )
        _send_transfer(conn, out, sku)


def _submit(out, call_id, reservation_id, encoded):
    _send(out, "gateway", {
        "kind": "submit",
        "origin": "source",
        "call_id": call_id,
        "reservation_id": reservation_id,
        "lines": json.loads(encoded),
    })


def _retry(conn, out):
    for call_id, reservation_id, encoded in conn.execute(
        "SELECT call_id,reservation_id,lines_json FROM bridge_calls WHERE acked=0 ORDER BY call_id"
    ).fetchall():
        _submit(out, call_id, reservation_id, encoded)
    for row in conn.execute(
        "SELECT sku FROM bridge_moves WHERE phase='fenced' ORDER BY sku"
    ).fetchall():
        _send_transfer(conn, out, row[0])


def on_message(conn, message):
    _schema(conn)
    out = {"messages": [], "replies": []}
    if not isinstance(message, dict):
        return out
    src = message.get("src")
    body = message.get("body", {})
    if not isinstance(body, dict):
        return out
    kind = body.get("kind")

    if src == "driver":
        if kind == "client":
            call_id = body.get("call_id")
            reservation_id = body.get("reservation_id")
            lines = body.get("lines")
            if isinstance(call_id, str) and call_id and _valid(conn, reservation_id, lines):
                encoded = _json(lines)
                conn.execute(
                    "INSERT OR IGNORE INTO bridge_calls(call_id,reservation_id,lines_json,acked) VALUES(?,?,?,0)",
                    (call_id, reservation_id, encoded),
                )
                saved = conn.execute(
                    "SELECT reservation_id,lines_json,acked FROM bridge_calls WHERE call_id=?",
                    (call_id,),
                ).fetchone()
                if saved[0] == reservation_id and saved[1] == encoded and not saved[2]:
                    _submit(out, call_id, reservation_id, encoded)
        elif kind == "reply_ack":
            call_id = body.get("call_id")
            if isinstance(call_id, str) and call_id:
                conn.execute(
                    "UPDATE bridge_calls SET acked=1 WHERE call_id=?",
                    (call_id,),
                )
        elif kind == "move":
            sku = body.get("sku")
            destination = body.get("destination")
            if isinstance(sku, str) and destination in ("A", "B"):
                stock = _stock(conn, sku)
                if stock is not None and stock[3]:
                    conn.execute(
                        "INSERT OR IGNORE INTO bridge_moves(sku,destination,epoch,phase) VALUES(?,?,?,'waiting')",
                        (sku, destination, stock[2] + 1),
                    )
                _send_transfer(conn, out, sku)
        elif kind == "init" and body.get("node_id") == "source":
            _retry(conn, out)
        elif kind == "tick":
            _retry(conn, out)
    elif src == "gateway":
        if kind == "prepare":
            _prepare(conn, out, body)
        elif kind == "decision":
            _decision(conn, out, body)
    elif src in ("A", "B") and kind == "installed":
        sku = body.get("sku")
        epoch = body.get("epoch")
        if isinstance(sku, str) and _valid_epoch(epoch):
            conn.execute(
                "UPDATE bridge_moves SET installed=1 WHERE sku=? AND destination=? AND epoch=? AND phase='fenced'",
                (sku, src, epoch),
            )

    _fence_ready(conn, out)
    unique = []
    seen = set()
    for packet in out["messages"]:
        encoded = _json(packet)
        if encoded not in seen:
            seen.add(encoded)
            unique.append(packet)
    out["messages"] = unique
    return out

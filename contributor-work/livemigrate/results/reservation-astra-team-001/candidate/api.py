import json


_MAX_SQL_INT = 9223372036854775807


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _schema(conn):
    statements = [
        "CREATE TABLE IF NOT EXISTS api_routes(sku TEXT PRIMARY KEY,owner TEXT NOT NULL,epoch INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS api_requests(seq INTEGER PRIMARY KEY AUTOINCREMENT,reservation_id TEXT NOT NULL UNIQUE,lines_json TEXT NOT NULL,state TEXT NOT NULL,finished INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS api_calls(call_id TEXT PRIMARY KEY,reservation_id TEXT NOT NULL,lines_json TEXT NOT NULL,origin TEXT NOT NULL,result TEXT,acked INTEGER NOT NULL DEFAULT 0,reply_sent INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE IF NOT EXISTS api_contacts(reservation_id TEXT NOT NULL,sku TEXT NOT NULL,owner TEXT NOT NULL,epoch INTEGER NOT NULL,voted_yes INTEGER NOT NULL DEFAULT 0,voted_no INTEGER NOT NULL DEFAULT 0,retired INTEGER NOT NULL DEFAULT 0,acked INTEGER NOT NULL DEFAULT 0,prepare_sent INTEGER NOT NULL DEFAULT 0,decision_sent INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(reservation_id,sku,owner,epoch))",
        "CREATE VIEW IF NOT EXISTS audit_decisions AS SELECT reservation_id,lines_json,state FROM api_requests WHERE state IN ('commit','abort')",
    ]
    for statement in statements:
        conn.execute(statement)


def _send(out, destination, body):
    out["messages"].append({"to": destination, "body": body})


def _initialize(conn, body):
    capacities = body.get("capacities", {})
    routing = body.get("routing", {})
    if not isinstance(capacities, dict) or not isinstance(routing, dict):
        return
    for sku in sorted(capacities):
        owner = routing.get(sku, "source")
        if isinstance(sku, str) and sku and owner in ("source", "A", "B"):
            conn.execute(
                "INSERT OR IGNORE INTO api_routes(sku,owner,epoch) VALUES(?,?,0)",
                (sku, owner),
            )


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
        if conn.execute("SELECT 1 FROM api_routes WHERE sku=?", (sku,)).fetchone() is None:
            return False
    return True


def _admit(conn, body, origin):
    call_id = body.get("call_id")
    reservation_id = body.get("reservation_id")
    lines = body.get("lines")
    if not isinstance(call_id, str) or not call_id:
        return
    if not _valid(conn, reservation_id, lines):
        return
    encoded = _json(lines)
    call = conn.execute(
        "SELECT reservation_id,lines_json FROM api_calls WHERE call_id=?",
        (call_id,),
    ).fetchone()
    if call is not None:
        if call[0] == reservation_id and call[1] == encoded:
            # A forwarding source may still need its own reply acknowledgement.
            conn.execute(
                "UPDATE api_calls SET acked=0,reply_sent=0 WHERE call_id=?",
                (call_id,),
            )
        return

    request = conn.execute(
        "SELECT lines_json FROM api_requests WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()
    result = None
    if request is None:
        # This is the global admission point for both public entry points.
        conn.execute(
            "INSERT INTO api_requests(reservation_id,lines_json,state) VALUES(?,?,'queued')",
            (reservation_id, encoded),
        )
    elif request[0] != encoded:
        result = "idempotency_conflict"
    conn.execute(
        "INSERT INTO api_calls(call_id,reservation_id,lines_json,origin,result) VALUES(?,?,?,?,?)",
        (call_id, reservation_id, encoded, origin, result),
    )


def _valid_epoch(epoch):
    return type(epoch) is int and 0 <= epoch <= _MAX_SQL_INT


def _adopt_route(conn, sender, sku, owner, epoch):
    if not isinstance(sku, str) or not _valid_epoch(epoch):
        return
    if owner == "source":
        if sender != "source" or epoch != 0:
            return
    elif owner in ("A", "B"):
        if sender not in ("source", owner) or epoch <= 0:
            return
    else:
        return
    previous = conn.execute(
        "SELECT owner,epoch FROM api_routes WHERE sku=?", (sku,)
    ).fetchone()
    if previous is None or epoch <= previous[1]:
        return
    conn.execute(
        "UPDATE api_routes SET owner=?,epoch=? WHERE sku=?",
        (owner, epoch, sku),
    )
    if owner in ("A", "B"):
        # The source's handoff protocol drains every prepared hold before
        # fencing. Its route, or the installed target's route, proves that
        # older source contacts have no unfinished tentative work. Preserve
        # their yes evidence: any such hold is now durably committed.
        conn.execute(
            "UPDATE api_contacts SET retired=1 WHERE sku=? AND owner='source' AND epoch<?",
            (sku, epoch),
        )


def _matching_request(conn, body):
    reservation_id = body.get("reservation_id")
    if not isinstance(reservation_id, str):
        return None
    request = conn.execute(
        "SELECT lines_json,state FROM api_requests WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()
    lines = body.get("lines")
    if request is None or not isinstance(lines, dict) or _json(lines) != request[0]:
        return None
    sku = body.get("sku")
    if not isinstance(sku, str) or sku not in lines:
        return None
    return reservation_id, sku, request[1]


def _vote(conn, sender, body):
    matched = _matching_request(conn, body)
    epoch = body.get("epoch")
    if matched is None or not _valid_epoch(epoch):
        return
    reservation_id, sku, state = matched
    vote = body.get("vote")
    if vote == "redirect":
        # A redirect carries the replacement epoch, not the attempted epoch.
        contacted = conn.execute(
            "SELECT 1 FROM api_contacts WHERE reservation_id=? AND sku=? AND owner=? LIMIT 1",
            (reservation_id, sku, sender),
        ).fetchone()
        if contacted is not None:
            _adopt_route(conn, sender, sku, body.get("owner"), epoch)
        return
    if state != "preparing":
        return
    contact = conn.execute(
        "SELECT 1 FROM api_contacts WHERE reservation_id=? AND sku=? AND owner=? AND epoch=?",
        (reservation_id, sku, sender, epoch),
    ).fetchone()
    if contact is None:
        return
    if vote == "yes":
        conn.execute(
            "UPDATE api_contacts SET voted_yes=1 WHERE reservation_id=? AND sku=? AND owner=? AND epoch=? AND voted_no=0",
            (reservation_id, sku, sender, epoch),
        )
    elif vote == "no":
        conn.execute(
            "UPDATE api_contacts SET voted_no=1 WHERE reservation_id=? AND sku=? AND owner=? AND epoch=? AND voted_yes=0",
            (reservation_id, sku, sender, epoch),
        )
    # Wait is transient. Participant identity conflicts cannot justify a
    # stock failure or replace the gateway's already admitted identity.


def _decision_ack(conn, sender, body):
    matched = _matching_request(conn, body)
    epoch = body.get("epoch")
    if matched is None or not _valid_epoch(epoch):
        return
    reservation_id, sku, state = matched
    if state not in ("commit", "abort") or body.get("decision") != state:
        return
    conn.execute(
        "UPDATE api_contacts SET acked=1 WHERE reservation_id=? AND sku=? AND owner=? AND epoch=?",
        (reservation_id, sku, sender, epoch),
    )


def _has_yes(conn, reservation_id, sku):
    return conn.execute(
        "SELECT 1 FROM api_contacts WHERE reservation_id=? AND sku=? AND voted_yes=1 LIMIT 1",
        (reservation_id, sku),
    ).fetchone() is not None


def _advance(conn):
    preparing = conn.execute(
        "SELECT reservation_id,lines_json FROM api_requests WHERE state='preparing' ORDER BY seq"
    ).fetchall()
    for reservation_id, encoded in preparing:
        rejected = conn.execute(
            "SELECT 1 FROM api_contacts WHERE reservation_id=? AND voted_no=1 LIMIT 1",
            (reservation_id,),
        ).fetchone()
        if rejected is not None:
            decision = "abort"
        elif all(_has_yes(conn, reservation_id, sku) for sku in json.loads(encoded)):
            decision = "commit"
        else:
            continue
        # Terminal state and its full payload are never subsequently changed.
        conn.execute(
            "UPDATE api_requests SET state=? WHERE reservation_id=? AND state='preparing'",
            (decision, reservation_id),
        )

    conn.execute(
        "UPDATE api_requests SET finished=1 WHERE finished=0 AND state IN ('commit','abort') "
        "AND NOT EXISTS (SELECT 1 FROM api_contacts c WHERE c.reservation_id=api_requests.reservation_id AND c.acked=0 AND c.retired=0)"
    )

    # FIFO admission among intersecting bundles avoids prepared-hold cycles.
    # Independent SKUs do not wait for each other's participant acknowledgements.
    occupied = set()
    unfinished = conn.execute(
        "SELECT reservation_id,lines_json,state FROM api_requests WHERE finished=0 ORDER BY seq"
    ).fetchall()
    for reservation_id, encoded, state in unfinished:
        skus = set(json.loads(encoded))
        if state == "queued" and not occupied.intersection(skus):
            conn.execute(
                "UPDATE api_requests SET state='preparing' WHERE reservation_id=? AND state='queued'",
                (reservation_id,),
            )
        occupied.update(skus)

    terminal = conn.execute(
        "SELECT reservation_id,lines_json,state,finished FROM api_requests WHERE state IN ('commit','abort')"
    ).fetchall()
    for reservation_id, encoded, state, finished in terminal:
        # Commit can acknowledge the irrevocable decision. Abort waits until
        # all possible tentative consumption is released or proved drained.
        if state == "abort" and not finished:
            continue
        result = "committed" if state == "commit" else "out_of_stock"
        conn.execute(
            "UPDATE api_calls SET result=?,reply_sent=0 WHERE reservation_id=? AND lines_json=? AND result IS NULL",
            (result, reservation_id, encoded),
        )


def _drive(conn, out, retry):
    requests = conn.execute(
        "SELECT reservation_id,lines_json,state FROM api_requests WHERE state IN ('preparing','commit','abort') ORDER BY seq"
    ).fetchall()
    for reservation_id, encoded, state in requests:
        lines = json.loads(encoded)
        if state == "preparing":
            for sku in sorted(lines):
                if _has_yes(conn, reservation_id, sku):
                    continue
                route = conn.execute(
                    "SELECT owner,epoch FROM api_routes WHERE sku=?", (sku,)
                ).fetchone()
                if route is None:
                    continue
                owner, epoch = route
                # Record every possible participant before emitting its prepare.
                conn.execute(
                    "INSERT OR IGNORE INTO api_contacts(reservation_id,sku,owner,epoch) VALUES(?,?,?,?)",
                    (reservation_id, sku, owner, epoch),
                )
                contact = conn.execute(
                    "SELECT prepare_sent,retired FROM api_contacts WHERE reservation_id=? AND sku=? AND owner=? AND epoch=?",
                    (reservation_id, sku, owner, epoch),
                ).fetchone()
                if contact[1] or (contact[0] and not retry):
                    continue
                conn.execute(
                    "UPDATE api_contacts SET prepare_sent=1 WHERE reservation_id=? AND sku=? AND owner=? AND epoch=?",
                    (reservation_id, sku, owner, epoch),
                )
                _send(out, owner, {
                    "kind": "prepare",
                    "reservation_id": reservation_id,
                    "lines": lines,
                    "sku": sku,
                    "qty": lines[sku],
                    "epoch": epoch,
                })
            continue

        contacts = conn.execute(
            "SELECT sku,owner,epoch,acked,retired,decision_sent FROM api_contacts WHERE reservation_id=? ORDER BY sku,epoch,owner",
            (reservation_id,),
        ).fetchall()
        for sku, owner, epoch, acked, retired, sent in contacts:
            if acked:
                continue
            if retired:
                # Notify even an old fenced contact once. Its drain certificate
                # makes further acknowledgements unnecessary for completion.
                if sent:
                    continue
            elif sent and not retry:
                continue
            conn.execute(
                "UPDATE api_contacts SET decision_sent=1 WHERE reservation_id=? AND sku=? AND owner=? AND epoch=?",
                (reservation_id, sku, owner, epoch),
            )
            _send(out, owner, {
                "kind": "decision",
                "reservation_id": reservation_id,
                "lines": lines,
                "sku": sku,
                "epoch": epoch,
                "decision": state,
            })


def _reply(conn, out, retry):
    calls = conn.execute(
        "SELECT call_id,reservation_id,lines_json,result,reply_sent FROM api_calls WHERE acked=0 AND result IS NOT NULL ORDER BY call_id"
    ).fetchall()
    for call_id, reservation_id, encoded, result, sent in calls:
        if sent and not retry:
            continue
        conn.execute(
            "UPDATE api_calls SET reply_sent=1 WHERE call_id=?", (call_id,)
        )
        out["replies"].append({
            "call_id": call_id,
            "reservation_id": reservation_id,
            "status": result,
            "lines": json.loads(encoded),
        })


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
    retry = False

    if sender == "driver":
        if kind == "init" and body.get("node_id") == "gateway":
            _initialize(conn, body)
        elif kind == "client":
            _admit(conn, body, "gateway")
        elif kind == "reply_ack":
            call_id = body.get("call_id")
            if isinstance(call_id, str) and call_id:
                conn.execute(
                    "UPDATE api_calls SET acked=1 WHERE call_id=?", (call_id,)
                )
        elif kind == "tick":
            retry = True
    elif sender in ("source", "A", "B"):
        if kind == "submit" and sender == "source" and body.get("origin") == "source":
            _admit(conn, body, "source")
        elif kind == "route":
            _adopt_route(conn, sender, body.get("sku"), body.get("owner"), body.get("epoch"))
        elif kind == "vote":
            _vote(conn, sender, body)
        elif kind == "decision_ack":
            _decision_ack(conn, sender, body)

    _advance(conn)
    _drive(conn, out, retry)
    _reply(conn, out, retry)
    return out

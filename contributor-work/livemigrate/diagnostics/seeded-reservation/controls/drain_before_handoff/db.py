"""Reference source participant, legacy adapter, and per-SKU ownership handoff."""
import json
import legacy


def on_message(conn, message):
    body, sender = message["body"], message["src"]
    messages, replies = [], []
    def send(to, **fields):
        messages.append({"to": to, "body": fields})
    def reply(call, status):
        replies.append({"call_id": call["call_id"], "reservation_id": call["reservation_id"], "lines": call["lines"], "status": status})
    for sql in [
        "CREATE TABLE IF NOT EXISTS moves(sku TEXT PRIMARY KEY,target TEXT,epoch INTEGER,state TEXT,snapshot TEXT)",
        "CREATE TABLE IF NOT EXISTS local_requests(reservation_id TEXT PRIMARY KEY,fingerprint TEXT,lines_json TEXT)",
        "CREATE TABLE IF NOT EXISTS aborted(reservation_id TEXT,sku TEXT,PRIMARY KEY(reservation_id,sku))",
        "CREATE TABLE IF NOT EXISTS client_calls(call_id TEXT PRIMARY KEY,payload TEXT)",
        "CREATE VIEW IF NOT EXISTS audit_inventory AS SELECT sku,total,available,epoch,CASE WHEN active=1 THEN 'active' ELSE 'fenced' END AS authority FROM legacy_stock",
        "CREATE VIEW IF NOT EXISTS audit_holds AS SELECT reservation_id,sku,qty,state FROM legacy_holds",
    ]:
        conn.execute(sql)
    kind = body["kind"]
    if kind == "client":
        conn.execute("INSERT OR IGNORE INTO client_calls VALUES(?,?)", (body["call_id"], json.dumps(body, sort_keys=True)))
    elif kind == "reply_ack":
        conn.execute("DELETE FROM client_calls WHERE call_id=?", (body["call_id"],))
    elif kind == "execute_legacy":
        known = conn.execute("SELECT 1 FROM legacy_requests WHERE reservation_id=?", (body["reservation_id"],)).fetchone()
        usable = all(conn.execute("SELECT active FROM legacy_stock WHERE sku=?", (sku,)).fetchone()[0] for sku in body["lines"])
        busy = any(conn.execute("SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared'", (sku,)).fetchone() for sku in body["lines"])
        if known or (usable and not busy):
            result = legacy.reserve(conn, body["reservation_id"], body["lines"])
            send("gateway", kind="legacy_result", reservation_id=body["reservation_id"], status=result["status"])
        else:
            send("gateway", kind="legacy_unavailable", reservation_id=body["reservation_id"])
    elif kind == "move":
        sku = body["sku"]
        if conn.execute("SELECT 1 FROM moves WHERE sku=?", (sku,)).fetchone() is None:
            stock = dict(conn.execute("SELECT * FROM legacy_stock WHERE sku=?", (sku,)).fetchone())
            epoch = stock["epoch"] + 1
            # Fence before snapshot: no source callback can mutate this SKU now.
            conn.execute("UPDATE legacy_stock SET active=0 WHERE sku=?", (sku,))
            requests = [dict(r) for r in conn.execute("SELECT reservation_id,fingerprint,lines_json FROM legacy_requests")]
            known = {r["reservation_id"] for r in requests}
            requests += [dict(r) for r in conn.execute("SELECT * FROM local_requests") if r["reservation_id"] not in known]
            snapshot = {"sku": sku, "total": stock["total"], "available": stock["available"], "epoch": epoch,
                        "holds": [dict(r) for r in conn.execute("SELECT * FROM legacy_holds WHERE sku=?", (sku,))],
                        "aborted": [r[0] for r in conn.execute("SELECT reservation_id FROM aborted WHERE sku=?", (sku,))], "requests": requests}
            conn.execute("INSERT INTO moves VALUES(?,?,?,'installing',?)", (sku, body["destination"], epoch, json.dumps(snapshot, sort_keys=True)))
    elif kind in ("ready", "activated"):
        move = conn.execute("SELECT * FROM moves WHERE sku=?", (body["sku"],)).fetchone()
        if move and sender == move["target"] and body["epoch"] == move["epoch"]:
            conn.execute("UPDATE moves SET state=? WHERE sku=?", ("activating" if kind == "ready" and move["state"] != "done" else "done" if kind == "activated" else move["state"], body["sku"]))
    elif kind in ("prepare", "commit", "abort"):
        rid, sku = body["reservation_id"], body["sku"]
        stock = conn.execute("SELECT * FROM legacy_stock WHERE sku=?", (sku,)).fetchone()
        if not stock["active"]:
            move = conn.execute("SELECT * FROM moves WHERE sku=?", (sku,)).fetchone()
            messages.append({"to": move["target"], "body": dict(body)})
        else:
            holder = conn.execute("SELECT * FROM legacy_holds WHERE reservation_id=? AND sku=?", (rid, sku)).fetchone()
            status = None
            if kind == "prepare":
                encoded = json.dumps(body["lines"], sort_keys=True, separators=(",", ":"))
                previous = conn.execute("SELECT fingerprint FROM legacy_requests WHERE reservation_id=?", (rid,)).fetchone()
                if previous is None:
                    previous = conn.execute("SELECT fingerprint FROM local_requests WHERE reservation_id=?", (rid,)).fetchone()
                if previous and previous[0] != encoded:
                    status = "conflict"
                elif conn.execute("SELECT 1 FROM aborted WHERE reservation_id=? AND sku=?", (rid, sku)).fetchone():
                    status = "aborted"
                elif holder and holder["state"] in ("prepared", "committed"):
                    status = "prepared"
                elif stock["available"] < body["qty"]:
                    status = "no_stock"
                else:
                    conn.execute("INSERT OR IGNORE INTO local_requests VALUES(?,?,?)", (rid, encoded, encoded))
                    conn.execute("INSERT OR REPLACE INTO legacy_holds VALUES(?,?,?,'prepared')", (rid, sku, body["qty"]))
                    conn.execute("UPDATE legacy_stock SET available=available-? WHERE sku=?", (body["qty"], sku))
                    status = "prepared"
            elif kind == "commit":
                if holder and holder["state"] in ("prepared", "committed"):
                    conn.execute("UPDATE legacy_holds SET state='committed' WHERE reservation_id=? AND sku=?", (rid, sku))
                    status = "committed"
                else:
                    status = "retry"
            else:
                if holder and holder["state"] == "committed":
                    status = "committed"
                else:
                    if holder and holder["state"] == "prepared":
                        conn.execute("UPDATE legacy_stock SET available=available+? WHERE sku=?", (holder["qty"], sku))
                        conn.execute("UPDATE legacy_holds SET state='released' WHERE reservation_id=? AND sku=?", (rid, sku))
                    conn.execute("INSERT OR IGNORE INTO aborted VALUES(?,?)", (rid, sku))
                    status = "aborted"
            send("gateway", kind=status, reservation_id=rid, sku=sku)
    # Durable state reconstructs every lost output; acknowledgements stop repeats.
    for move in conn.execute("SELECT * FROM moves ORDER BY sku"):
        if move["state"] == "installing":
            send(move["target"], kind="install", snapshot=json.loads(move["snapshot"]))
        elif move["state"] == "activating":
            send(move["target"], kind="activate", sku=move["sku"], epoch=move["epoch"])
    for row in conn.execute("SELECT * FROM client_calls ORDER BY call_id").fetchall():
        call = json.loads(row["payload"])
        known = conn.execute("SELECT 1 FROM legacy_requests WHERE reservation_id=?", (call["reservation_id"],)).fetchone()
        if known:
            reply(call, legacy.reserve(conn, call["reservation_id"], call["lines"])["status"])
        else:
            # Global identity admission precedes every new legacy execution.
            # This remains necessary even for an unmoved SKU after handoff.
            messages.append({"to": "gateway", "body": dict(call, legacy=True)})
    return {"messages": messages, "replies": replies}


_base = on_message
def on_message(conn, message):
    import json
    conn.execute('CREATE TABLE IF NOT EXISTS deferred_moves(sku TEXT PRIMARY KEY,payload TEXT)')
    body = message['body']
    if body['kind'] == 'move' and conn.execute("SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared'", (body['sku'],)).fetchone():
        conn.execute('INSERT OR REPLACE INTO deferred_moves VALUES(?,?)', (body['sku'], json.dumps(message)))
        result = _base(conn, {'src':'driver','body':{'kind':'tick'}})
    else:
        result = _base(conn, message)
    for row in conn.execute('SELECT * FROM deferred_moves').fetchall():
        if not conn.execute("SELECT 1 FROM legacy_holds WHERE sku=? AND state='prepared'", (row['sku'],)).fetchone():
            conn.execute('DELETE FROM deferred_moves WHERE sku=?', (row['sku'],))
            extra = _base(conn, json.loads(row['payload']))
            result['messages'] += extra['messages']
            result['replies'] += extra['replies']
    return result

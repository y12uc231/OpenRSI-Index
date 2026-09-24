"""Reference durable coordinator with disjoint-SKU progress and retryable 2PC."""
import json


def on_message(conn, message):
    body = message["body"]
    messages, replies = [], []
    def send(to, **fields):
        messages.append({"to": to, "body": fields})
    for sql in [
        "CREATE TABLE IF NOT EXISTS routes(sku TEXT PRIMARY KEY,owner TEXT,epoch INTEGER)",
        "CREATE TABLE IF NOT EXISTS transactions(reservation_id TEXT PRIMARY KEY,lines_json TEXT,state TEXT,reason TEXT,ordinal INTEGER,legacy INTEGER)",
        "CREATE TABLE IF NOT EXISTS votes(reservation_id TEXT,sku TEXT,prepared INTEGER DEFAULT 0,finished INTEGER DEFAULT 0,PRIMARY KEY(reservation_id,sku))",
        "CREATE TABLE IF NOT EXISTS calls(call_id TEXT PRIMARY KEY,reservation_id TEXT,lines_json TEXT,conflict INTEGER DEFAULT 0)",
        "CREATE VIEW IF NOT EXISTS audit_decisions AS SELECT reservation_id,lines_json,CASE WHEN state IN ('committing','committed') THEN 'commit' ELSE 'abort' END AS state FROM transactions WHERE state IN ('committing','committed','aborting','rejected')",
    ]:
        conn.execute(sql)
    kind = body["kind"]
    if kind == "init":
        for sku in body["capacities"]:
            conn.execute("INSERT OR IGNORE INTO routes VALUES(?,'source',0)", (sku,))
    elif kind == "route":
        old = conn.execute("SELECT epoch FROM routes WHERE sku=?", (body["sku"],)).fetchone()
        if old and body["epoch"] > old[0]:
            conn.execute("UPDATE routes SET owner=?,epoch=? WHERE sku=?", (body["owner"], body["epoch"], body["sku"]))
    elif kind == "client":
        rid = body["reservation_id"]
        encoded = json.dumps(body["lines"], sort_keys=True, separators=(",", ":"))
        old = conn.execute("SELECT * FROM transactions WHERE reservation_id=?", (rid,)).fetchone()
        if old is None:
            ordinal = conn.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM transactions").fetchone()[0]
            conn.execute("INSERT INTO transactions VALUES(?,?,'queued',NULL,?,?)", (rid, encoded, ordinal, int(bool(body.get("legacy")))))
            for sku in body["lines"]:
                conn.execute("INSERT INTO votes(reservation_id,sku) VALUES(?,?)", (rid, sku))
        conflict = int(old is not None and old["lines_json"] != encoded)
        conn.execute("INSERT OR IGNORE INTO calls VALUES(?,?,?,?)", (body["call_id"], rid, encoded, conflict))
    elif kind == "reply_ack":
        conn.execute("DELETE FROM calls WHERE call_id=?", (body["call_id"],))
    elif kind in ("legacy_result", "legacy_unavailable"):
        tx = conn.execute("SELECT * FROM transactions WHERE reservation_id=?", (body["reservation_id"],)).fetchone()
        if tx and tx["state"] == "legacy_running":
            if kind == "legacy_unavailable":
                conn.execute("UPDATE transactions SET state='preparing' WHERE reservation_id=?", (body["reservation_id"],))
            else:
                status = body["status"]
                conn.execute("UPDATE transactions SET state=?,reason=? WHERE reservation_id=?", ("committed" if status == "committed" else "rejected", None if status == "committed" else status, body["reservation_id"]))
    elif kind in ("prepared", "committed", "aborted", "no_stock", "conflict", "retry"):
        rid = body["reservation_id"]
        tx = conn.execute("SELECT * FROM transactions WHERE reservation_id=?", (rid,)).fetchone()
        if tx:
            if kind == "prepared" and tx["state"] == "preparing":
                conn.execute("UPDATE votes SET prepared=1 WHERE reservation_id=? AND sku=?", (rid, body["sku"]))
            elif kind in ("no_stock", "conflict") and tx["state"] == "preparing":
                conn.execute("UPDATE transactions SET state='aborting',reason=? WHERE reservation_id=?", ("out_of_stock" if kind == "no_stock" else "idempotency_conflict", rid))
                conn.execute("UPDATE votes SET finished=0 WHERE reservation_id=?", (rid,))
            elif (kind == "committed" and tx["state"] == "committing") or (kind == "aborted" and tx["state"] == "aborting"):
                conn.execute("UPDATE votes SET finished=1 WHERE reservation_id=? AND sku=?", (rid, body["sku"]))
    # Start unrelated queued transactions even if another SKU is transferring.
    busy = set()
    for row in conn.execute("SELECT lines_json FROM transactions WHERE state IN ('preparing','committing','aborting','legacy_running')"):
        busy.update(json.loads(row[0]))
    for tx in conn.execute("SELECT * FROM transactions WHERE state='queued' ORDER BY ordinal").fetchall():
        lines = json.loads(tx["lines_json"])
        if not busy.intersection(lines):
            conn.execute("UPDATE transactions SET state=? WHERE reservation_id=?", ("legacy_running" if tx["legacy"] else "preparing", tx["reservation_id"]))
            busy.update(lines)
    for tx in conn.execute("SELECT * FROM transactions ORDER BY ordinal").fetchall():
        rid, state = tx["reservation_id"], tx["state"]
        votes = conn.execute("SELECT * FROM votes WHERE reservation_id=?", (rid,)).fetchall()
        if state == "preparing" and all(v["prepared"] for v in votes):
            state = "committing"
            conn.execute("UPDATE transactions SET state='committing' WHERE reservation_id=?", (rid,))
        elif state in ("committing", "aborting") and all(v["finished"] for v in votes):
            state = "committed" if state == "committing" else "rejected"
            conn.execute("UPDATE transactions SET state=? WHERE reservation_id=?", (state, rid))
        lines = json.loads(tx["lines_json"])
        if state == "legacy_running":
            send("source", kind="execute_legacy", reservation_id=rid, lines=lines)
        if state in ("preparing", "committing", "aborting"):
            action = {"preparing": "prepare", "committing": "commit", "aborting": "abort"}[state]
            for vote in votes:
                if (state == "preparing" and vote["prepared"]) or (state != "preparing" and vote["finished"]):
                    continue
                owner = conn.execute("SELECT owner FROM routes WHERE sku=?", (vote["sku"],)).fetchone()[0]
                send(owner, kind=action, reservation_id=rid, sku=vote["sku"], qty=lines[vote["sku"]], lines=lines)
    for call in conn.execute("SELECT calls.*,transactions.state,transactions.reason FROM calls JOIN transactions USING(reservation_id)"):
        if call["conflict"] or call["state"] in ("committed", "rejected"):
            status = "idempotency_conflict" if call["conflict"] else "committed" if call["state"] == "committed" else call["reason"]
            replies.append({"call_id": call["call_id"], "reservation_id": call["reservation_id"], "lines": json.loads(call["lines_json"]), "status": status})
    return {"messages": messages, "replies": replies}

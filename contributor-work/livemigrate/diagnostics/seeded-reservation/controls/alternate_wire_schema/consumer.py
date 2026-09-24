"""Reference owner: staged imports, durable escrow and replayable decisions."""
import json


def on_message(conn, message):
    body = message["body"]
    messages = []
    def send(to, **fields):
        messages.append({"to": to, "body": fields})
    for sql in [
        "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)",
        "CREATE TABLE IF NOT EXISTS target_inventory(sku TEXT PRIMARY KEY,total INTEGER,available INTEGER,epoch INTEGER,authority TEXT)",
        "CREATE TABLE IF NOT EXISTS holds(reservation_id TEXT,sku TEXT,qty INTEGER,state TEXT,PRIMARY KEY(reservation_id,sku))",
        "CREATE TABLE IF NOT EXISTS receipts(reservation_id TEXT PRIMARY KEY,fingerprint TEXT,lines_json TEXT)",
        "CREATE TABLE IF NOT EXISTS aborted(reservation_id TEXT,sku TEXT,PRIMARY KEY(reservation_id,sku))",
        "CREATE VIEW IF NOT EXISTS audit_inventory AS SELECT * FROM target_inventory",
        "CREATE VIEW IF NOT EXISTS audit_holds AS SELECT * FROM holds",
    ]:
        conn.execute(sql)
    kind = body["kind"]
    if kind == "init":
        conn.execute("INSERT OR REPLACE INTO settings VALUES('node',?)", (body["node_id"],))
    node = conn.execute("SELECT value FROM settings WHERE key='node'").fetchone()[0]
    if kind == "install":
        snap = body["snapshot"]
        old = conn.execute("SELECT * FROM target_inventory WHERE sku=?", (snap["sku"],)).fetchone()
        if old is None:
            conn.execute("INSERT INTO target_inventory VALUES(?,?,?,?,'staged')", (snap["sku"], snap["total"], snap["available"], snap["epoch"]))
            for row in snap["holds"]:
                conn.execute("INSERT INTO holds VALUES(?,?,?,?)", (row["reservation_id"], row["sku"], row["qty"], row["state"]))
            for rid in snap["aborted"]:
                conn.execute("INSERT OR IGNORE INTO aborted VALUES(?,?)", (rid, snap["sku"]))
            for row in snap["requests"]:
                previous = conn.execute("SELECT fingerprint FROM receipts WHERE reservation_id=?", (row["reservation_id"],)).fetchone()
                if previous and previous[0] != row["fingerprint"]:
                    raise ValueError("inconsistent immutable imported receipt")
                conn.execute("INSERT OR IGNORE INTO receipts VALUES(?,?,?)", (row["reservation_id"], row["fingerprint"], row["lines_json"]))
        if old is None or old["epoch"] == snap["epoch"]:
            send("source", kind="ready", sku=snap["sku"], epoch=snap["epoch"])
    elif kind == "activate":
        stock = conn.execute("SELECT * FROM target_inventory WHERE sku=?", (body["sku"],)).fetchone()
        if stock and stock["epoch"] == body["epoch"]:
            conn.execute("UPDATE target_inventory SET authority='active' WHERE sku=?", (body["sku"],))
            send("source", kind="activated", sku=body["sku"], epoch=body["epoch"])
    elif kind in ("prepare", "commit", "abort"):
        rid, sku = body["reservation_id"], body["sku"]
        stock = conn.execute("SELECT * FROM target_inventory WHERE sku=?", (sku,)).fetchone()
        holder = conn.execute("SELECT * FROM holds WHERE reservation_id=? AND sku=?", (rid, sku)).fetchone()
        if not stock or stock["authority"] != "active":
            status = "retry"
        elif kind == "prepare":
            encoded = json.dumps(body["lines"], sort_keys=True, separators=(",", ":"))
            previous = conn.execute("SELECT fingerprint FROM receipts WHERE reservation_id=?", (rid,)).fetchone()
            if previous and previous[0] != encoded:
                status = "conflict"
            elif conn.execute("SELECT 1 FROM aborted WHERE reservation_id=? AND sku=?", (rid, sku)).fetchone():
                status = "aborted"
            elif holder and holder["state"] in ("prepared", "committed"):
                status = "prepared"
            elif stock["available"] < body["qty"]:
                status = "no_stock"
            else:
                conn.execute("INSERT OR IGNORE INTO receipts VALUES(?,?,?)", (rid, encoded, encoded))
                conn.execute("INSERT OR REPLACE INTO holds VALUES(?,?,?,'prepared')", (rid, sku, body["qty"]))
                conn.execute("UPDATE target_inventory SET available=available-? WHERE sku=?", (body["qty"], sku))
                status = "prepared"
        elif kind == "commit":
            if holder and holder["state"] in ("prepared", "committed"):
                conn.execute("UPDATE holds SET state='committed' WHERE reservation_id=? AND sku=?", (rid, sku))
                status = "committed"
            else:
                status = "retry"
        elif holder and holder["state"] == "committed":
            status = "committed"
        else:
            if holder and holder["state"] == "prepared":
                conn.execute("UPDATE target_inventory SET available=available+? WHERE sku=?", (holder["qty"], sku))
                conn.execute("UPDATE holds SET state='released' WHERE reservation_id=? AND sku=?", (rid, sku))
            conn.execute("INSERT OR IGNORE INTO aborted VALUES(?,?)", (rid, sku))
            status = "aborted"
        send("gateway", kind=status, reservation_id=rid, sku=sku)
    # Fresh routing advertisement is also sufficient after source retirement.
    for stock in conn.execute("SELECT * FROM target_inventory WHERE authority='active'"):
        send("gateway", kind="route", sku=stock["sku"], owner=node, epoch=stock["epoch"])
    return {"messages": messages, "replies": []}


_base = on_message
def on_message(conn, message):
    import copy
    message = copy.deepcopy(message)
    if 'verb' in message['body']:
        message['body']['kind'] = message['body'].pop('verb')[len('alternate:'):]
    result = _base(conn, message)
    for packet in result['messages']:
        packet['body']['verb'] = 'alternate:' + packet['body'].pop('kind')
    return result

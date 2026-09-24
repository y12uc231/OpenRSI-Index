"""Reference v2 API with dual writes and immutable payment event snapshots."""
import json


def handle(conn, request, phase):
    order = conn.execute("SELECT * FROM orders WHERE order_id=?", (request["order_id"],)).fetchone()
    op = request["op"]
    if op == "get":
        amount = order["amount_micros"]
        if amount is None:
            amount = order["amount_cents"] * 10000
        return {"ok": True, "order_id": order["order_id"], "revision": order["revision"], "amount_micros": amount}
    if op == "pay":
        previous = conn.execute("SELECT * FROM payments WHERE payment_id=?", (request["payment_id"],)).fetchone()
        if previous is not None:
            if previous["order_id"] != request["order_id"] or previous["order_revision"] != request["expected_revision"]:
                return {"ok": False, "error": "idempotency_conflict"}
            return {"ok": True, "payment_id": request["payment_id"]}
    revision = 0 if order is None else order["revision"]
    if revision != request["expected_revision"]:
        return {"ok": False, "error": "revision_conflict"}
    if op == "put":
        amount = request["amount_micros"]
        if phase == "overlap":
            if amount % 10000:
                return {"ok": False, "error": "legacy_precision"}
            if order is None:
                conn.execute("INSERT INTO orders(order_id,revision,amount_cents,amount_micros) VALUES(?,?,?,?)", (request["order_id"], revision + 1, amount // 10000, amount))
            else:
                conn.execute("UPDATE orders SET revision=?,amount_cents=?,amount_micros=? WHERE order_id=?", (revision + 1, amount // 10000, amount, request["order_id"]))
        elif order is None:
            conn.execute("INSERT INTO orders(order_id,revision,amount_micros) VALUES(?,?,?)", (request["order_id"], revision + 1, amount))
        else:
            conn.execute("UPDATE orders SET revision=?,amount_micros=? WHERE order_id=?", (revision + 1, amount, request["order_id"]))
        return {"ok": True, "revision": revision + 1}
    if op != "pay":
        raise ValueError("unknown request operation")
    amount = order["amount_micros"]
    if amount is None:
        amount = order["amount_cents"] * 10000
    payload = {"payment_id": request["payment_id"], "order_id": order["order_id"], "order_revision": revision, "amount_micros": amount}
    if phase == "overlap":
        payload["amount_cents"] = amount // 10000
        conn.execute("INSERT INTO payments(payment_id,order_id,order_revision,amount_cents,amount_micros) VALUES(?,?,?,?,?)", (payload["payment_id"], payload["order_id"], revision, amount // 10000, amount))
    else:
        conn.execute("INSERT INTO payments(payment_id,order_id,order_revision,amount_micros) VALUES(?,?,?,?)", (payload["payment_id"], payload["order_id"], revision, amount))
    conn.execute("INSERT INTO outbox(event_id,payment_id,version,payload) VALUES(?,?,2,?)", (payload["payment_id"], payload["payment_id"], json.dumps(payload, sort_keys=True)))
    return {"ok": True, "payment_id": payload["payment_id"]}

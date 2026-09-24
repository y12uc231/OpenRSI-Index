"""Frozen legacy service. This file is not a candidate-owned artifact."""
import json


def handle(conn, request, phase=None):
    op = request["op"]
    order = conn.execute("SELECT * FROM orders WHERE order_id=?", (request["order_id"],)).fetchone()
    if op == "get":
        return {"ok": True, "order_id": order["order_id"], "revision": order["revision"], "amount_cents": order["amount_cents"]}
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
        if order is None:
            conn.execute("INSERT INTO orders(order_id,amount_cents,revision) VALUES(?,?,?)", (request["order_id"], request["amount_cents"], revision + 1))
        else:
            conn.execute("UPDATE orders SET amount_cents=?,revision=? WHERE order_id=?", (request["amount_cents"], revision + 1, request["order_id"]))
        return {"ok": True, "revision": revision + 1}
    if op != "pay":
        raise ValueError("unknown request operation")
    payload = {"payment_id": request["payment_id"], "order_id": order["order_id"], "order_revision": revision, "amount_cents": order["amount_cents"]}
    conn.execute("INSERT INTO payments(payment_id,order_id,order_revision,amount_cents) VALUES(?,?,?,?)", (payload["payment_id"], payload["order_id"], revision, payload["amount_cents"]))
    conn.execute("INSERT INTO outbox(event_id,payment_id,version,payload) VALUES(?,?,1,?)", (payload["payment_id"], payload["payment_id"], json.dumps(payload, sort_keys=True)))
    return {"ok": True, "payment_id": payload["payment_id"]}


def consume(conn, event):
    payload = event["payload"]
    return {"payment_id": payload["payment_id"], "idempotency_key": payload["payment_id"], "amount_micros": payload["amount_cents"] * 10000}

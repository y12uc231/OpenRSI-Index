"""Reference mixed-version, replay-safe payment consumer."""


def consume(conn, event):
    payload = event["payload"]
    amount = payload["amount_cents"] * 10000 if event["version"] == 1 else payload["amount_micros"]
    return {"payment_id": payload["payment_id"], "idempotency_key": payload["payment_id"], "amount_micros": amount}

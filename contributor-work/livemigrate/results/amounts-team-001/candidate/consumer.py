"""Consume immutable payment snapshots with replay-safe settlement keys."""


def consume(conn, event):
    payload = event["payload"]
    payment_id = payload["payment_id"]
    version = event["version"]

    if version == 1:
        amount_micros = payload["amount_cents"] * 10000
    elif version == 2:
        amount_micros = payload["amount_micros"]
    else:
        raise ValueError("unsupported event version")

    return {
        "payment_id": payment_id,
        "idempotency_key": payment_id,
        "amount_micros": amount_micros,
    }

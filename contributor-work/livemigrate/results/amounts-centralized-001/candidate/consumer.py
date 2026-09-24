"""Consume immutable event snapshots using the legacy deduplication key."""


def consume(conn, event):
    payload = event['payload']
    if event['version'] == 1:
        amount = payload['amount_cents'] * 10000
    elif event['version'] == 2:
        amount = payload['amount_micros']
    else:
        raise ValueError('unsupported event version')
    payment_id = payload['payment_id']
    return {
        'payment_id': payment_id,
        'idempotency_key': payment_id,
        'amount_micros': amount,
    }

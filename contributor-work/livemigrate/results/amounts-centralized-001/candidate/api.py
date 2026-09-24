"""Version-two API with legacy-compatible writes and snapshot payments."""

import json


def _has_cents(conn, table):
    return any(row[1] == 'amount_cents'
               for row in conn.execute('PRAGMA table_info(' + table + ')'))


def handle(conn, request, phase):
    op = request['op']
    if op not in ('put', 'get', 'pay'):
        raise ValueError('unknown request operation')

    # Check the accepted request identity before consulting the current order.
    if op == 'pay':
        previous = conn.execute(
            'SELECT order_id, order_revision FROM payments WHERE payment_id = ?',
            (request['payment_id'],),
        ).fetchone()
        if previous is not None:
            if (previous[0] != request['order_id'] or
                    previous[1] != request['expected_revision']):
                return {'ok': False, 'error': 'idempotency_conflict'}
            return {'ok': True, 'payment_id': request['payment_id']}

    order_has_cents = _has_cents(conn, 'orders')
    amount_column = 'amount_cents' if order_has_cents else 'amount_micros'
    order = conn.execute(
        'SELECT revision, ' + amount_column + ' FROM orders WHERE order_id = ?',
        (request['order_id'],),
    ).fetchone()

    if op == 'get':
        if order is None:
            return {'ok': False, 'error': 'not_found'}
        amount = order[1] * 10000 if order_has_cents else order[1]
        return {
            'ok': True,
            'order_id': request['order_id'],
            'revision': order[0],
            'amount_micros': amount,
        }

    revision = 0 if order is None else order[0]
    if revision != request['expected_revision']:
        return {'ok': False, 'error': 'revision_conflict'}

    if op == 'put':
        amount = request['amount_micros']
        if order_has_cents and amount % 10000:
            raise ValueError('the coexistence schema requires an exact cent amount')
        next_revision = revision + 1
        if order is None:
            if order_has_cents:
                conn.execute(
                    'INSERT INTO orders '
                    '(order_id, amount_cents, amount_micros, revision) VALUES (?, ?, ?, ?)',
                    (request['order_id'], amount // 10000, amount, next_revision),
                )
            else:
                conn.execute(
                    'INSERT INTO orders (order_id, amount_micros, revision) VALUES (?, ?, ?)',
                    (request['order_id'], amount, next_revision),
                )
        elif order_has_cents:
            conn.execute(
                'UPDATE orders SET amount_cents = ?, amount_micros = ?, revision = ? '
                'WHERE order_id = ?',
                (amount // 10000, amount, next_revision, request['order_id']),
            )
        else:
            conn.execute(
                'UPDATE orders SET amount_micros = ?, revision = ? WHERE order_id = ?',
                (amount, next_revision, request['order_id']),
            )
        return {'ok': True, 'revision': next_revision}

    if order is None:
        return {'ok': False, 'error': 'revision_conflict'}

    amount = order[1] * 10000 if order_has_cents else order[1]
    payment_id = request['payment_id']
    payload = {
        'payment_id': payment_id,
        'order_id': request['order_id'],
        'order_revision': revision,
        'amount_micros': amount,
    }
    if phase == 'overlap':
        if amount % 10000:
            raise ValueError('overlap events require an exact cent projection')
        payload['amount_cents'] = amount // 10000

    if _has_cents(conn, 'payments'):
        if amount % 10000:
            raise ValueError('the coexistence schema requires an exact cent snapshot')
        conn.execute(
            'INSERT INTO payments '
            '(payment_id, order_id, order_revision, amount_cents, amount_micros) '
            'VALUES (?, ?, ?, ?, ?)',
            (payment_id, request['order_id'], revision, amount // 10000, amount),
        )
    else:
        conn.execute(
            'INSERT INTO payments '
            '(payment_id, order_id, order_revision, amount_micros) VALUES (?, ?, ?, ?)',
            (payment_id, request['order_id'], revision, amount),
        )
    conn.execute(
        'INSERT INTO outbox (event_id, payment_id, version, payload) VALUES (?, ?, 2, ?)',
        (payment_id, payment_id, json.dumps(payload, sort_keys=True)),
    )
    return {'ok': True, 'payment_id': payment_id}

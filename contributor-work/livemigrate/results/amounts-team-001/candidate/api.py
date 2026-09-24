"""Live-compatible v2 order API; transaction ownership remains with the caller."""
import json


MICROS_PER_CENT = 10000


def _columns(conn, table):
    # Table names come only from constants within this module.
    return {row[1] for row in conn.execute('PRAGMA table_info(' + table + ')')}


def _amount_fields(columns, amount_micros):
    fields = {}
    if 'amount_cents' in columns:
        if amount_micros % MICROS_PER_CENT:
            raise ValueError('expanded schema requires an exact cents projection')
        fields['amount_cents'] = amount_micros // MICROS_PER_CENT
    if 'amount_micros' in columns:
        fields['amount_micros'] = amount_micros
    if not fields:
        raise RuntimeError('missing amount representation')
    return fields


def _insert(conn, table, fields):
    names = list(fields)
    conn.execute(
        'INSERT INTO ' + table + '(' + ','.join(names) + ') VALUES('
        + ','.join('?' for _ in names) + ')',
        tuple(fields[name] for name in names),
    )


def handle(conn, request, phase):
    if phase not in ('overlap', 'v2_only'):
        raise ValueError('unknown migration phase')
    op = request['op']
    if op not in ('get', 'put', 'pay'):
        raise ValueError('unknown request operation')

    order_id = request['order_id']

    # Idempotency precedes checking the current order: a successful payment
    # remains retryable after subsequent order revisions.
    if op == 'pay':
        payment_id = request['payment_id']
        previous = conn.execute(
            'SELECT order_id,order_revision FROM payments WHERE payment_id=?',
            (payment_id,),
        ).fetchone()
        if previous is not None:
            if (previous[0] != order_id
                    or previous[1] != request['expected_revision']):
                return {'ok': False, 'error': 'idempotency_conflict'}
            return {'ok': True, 'payment_id': payment_id}

    order_columns = _columns(conn, 'orders')
    # Legacy writers may leave a populated micros shadow stale. Cents stay
    # authoritative until contraction reconciles and removes that column.
    amount_column = (
        'amount_cents' if 'amount_cents' in order_columns else 'amount_micros'
    )
    order = conn.execute(
        'SELECT order_id,revision,' + amount_column
        + ' FROM orders WHERE order_id=?',
        (order_id,),
    ).fetchone()

    if op == 'get':
        if order is None:
            return {'ok': False, 'error': 'not_found'}
        amount_micros = order[2]
        if amount_column == 'amount_cents':
            amount_micros *= MICROS_PER_CENT
        return {
            'ok': True,
            'order_id': order[0],
            'revision': order[1],
            'amount_micros': amount_micros,
        }

    revision = 0 if order is None else order[1]
    if (revision != request['expected_revision']
            or (op == 'pay' and order is None)):
        return {'ok': False, 'error': 'revision_conflict'}

    if op == 'put':
        amount_micros = request['amount_micros']
        if type(amount_micros) is not int or amount_micros <= 0:
            raise ValueError('amount_micros must be a positive integer')
        if phase == 'overlap' and amount_micros % MICROS_PER_CENT:
            raise ValueError('overlap requires whole-cent amounts')
        fields = {'revision': revision + 1}
        fields.update(_amount_fields(order_columns, amount_micros))
        if order is None:
            fields['order_id'] = order_id
            _insert(conn, 'orders', fields)
        else:
            names = list(fields)
            conn.execute(
                'UPDATE orders SET '
                + ','.join(name + '=?' for name in names)
                + ' WHERE order_id=?',
                tuple(fields[name] for name in names) + (order_id,),
            )
        return {'ok': True, 'revision': revision + 1}

    amount_micros = order[2]
    if amount_column == 'amount_cents':
        amount_micros *= MICROS_PER_CENT
    payload = {
        'payment_id': payment_id,
        'order_id': order[0],
        'order_revision': revision,
        'amount_micros': amount_micros,
    }
    if phase == 'overlap':
        if amount_micros % MICROS_PER_CENT:
            raise ValueError('overlap requires whole-cent amounts')
        payload['amount_cents'] = amount_micros // MICROS_PER_CENT

    payment = {
        'payment_id': payment_id,
        'order_id': order[0],
        'order_revision': revision,
    }
    payment.update(_amount_fields(_columns(conn, 'payments'), amount_micros))
    encoded_payload = json.dumps(payload, sort_keys=True)
    _insert(conn, 'payments', payment)
    conn.execute(
        'INSERT INTO outbox(event_id,payment_id,version,payload) VALUES(?,?,2,?)',
        (payment_id, payment_id, encoded_payload),
    )
    return {'ok': True, 'payment_id': payment_id}

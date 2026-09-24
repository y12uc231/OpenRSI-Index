"""Expand, incrementally backfill, and contract the amount migration."""


def _columns(conn, table):
    return {row[1] for row in conn.execute('PRAGMA table_info(' + table + ')')}


def expand(conn):
    legacy_tables = []
    for table, identity in (('orders', 'order_id'), ('payments', 'payment_id')):
        columns = _columns(conn, table)
        if 'amount_cents' not in columns:
            continue
        if 'amount_micros' not in columns:
            conn.execute('ALTER TABLE ' + table + ' ADD COLUMN amount_micros INTEGER')
        legacy_tables.append((table, identity))

    if not legacy_tables:
        return

    # Persist a stable enumeration of preexisting rows across callback restarts.
    conn.execute('''CREATE TABLE IF NOT EXISTS _amount_backfill (
        position INTEGER PRIMARY KEY,
        table_name TEXT NOT NULL,
        item_id TEXT NOT NULL,
        UNIQUE(table_name, item_id)
    )''')
    for table, identity in legacy_tables:
        conn.execute(
            'INSERT OR IGNORE INTO _amount_backfill(table_name, item_id) '
            'SELECT ?, ' + identity + ' FROM ' + table + ' ORDER BY ' + identity,
            (table,),
        )


def backfill(conn, cursor, limit):
    if limit <= 0:
        raise ValueError('limit must be positive')
    legacy_tables = {
        table for table in ('orders', 'payments')
        if 'amount_cents' in _columns(conn, table)
    }
    if not legacy_tables:
        return {'cursor': cursor, 'done': True}

    rows = conn.execute(
        'SELECT position, table_name, item_id FROM _amount_backfill '
        'WHERE position > ? ORDER BY position LIMIT ?',
        (cursor, limit),
    ).fetchall()
    next_cursor = cursor
    for position, table, item_id in rows:
        if table in legacy_tables:
            identity = 'order_id' if table == 'orders' else 'payment_id'
            conn.execute(
                'UPDATE ' + table + ' SET amount_micros = amount_cents * 10000 '
                'WHERE ' + identity + ' = ?',
                (item_id,),
            )
        next_cursor = position

    remaining = conn.execute(
        'SELECT 1 FROM _amount_backfill WHERE position > ? LIMIT 1',
        (next_cursor,),
    ).fetchone()
    return {'cursor': next_cursor, 'done': remaining is None}


def contract(conn):
    # Reconcile legacy writes made after any backfill chunk, including rollback.
    # Payment amounts come from their own immutable snapshots.
    if 'amount_cents' in _columns(conn, 'orders'):
        conn.execute('''CREATE TABLE _amount_orders_replacement (
            order_id TEXT PRIMARY KEY,
            amount_micros INTEGER NOT NULL,
            revision INTEGER NOT NULL
        )''')
        conn.execute('''INSERT INTO _amount_orders_replacement
            (order_id, amount_micros, revision)
            SELECT order_id, amount_cents * 10000, revision FROM orders''')
        conn.execute('DROP TABLE orders')
        conn.execute('ALTER TABLE _amount_orders_replacement RENAME TO orders')

    if 'amount_cents' in _columns(conn, 'payments'):
        conn.execute('''CREATE TABLE _amount_payments_replacement (
            payment_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            order_revision INTEGER NOT NULL,
            amount_micros INTEGER NOT NULL
        )''')
        conn.execute('''INSERT INTO _amount_payments_replacement
            (payment_id, order_id, order_revision, amount_micros)
            SELECT payment_id, order_id, order_revision, amount_cents * 10000
            FROM payments''')
        conn.execute('DROP TABLE payments')
        conn.execute('ALTER TABLE _amount_payments_replacement RENAME TO payments')

    conn.execute('DROP TABLE IF EXISTS _amount_backfill')

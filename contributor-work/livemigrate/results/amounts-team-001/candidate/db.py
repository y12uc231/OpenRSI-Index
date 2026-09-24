"""Live migration with cents authoritative until contraction."""

_TABLES = (("orders", "order_id"), ("payments", "payment_id"))
_QUEUE = "_lm_micros_backfill"


def _columns(conn, table):
    return {row[1] for row in conn.execute('PRAGMA table_info("%s")' % table)}


def expand(conn):
    legacy_tables = [
        (kind, table, key)
        for kind, (table, key) in enumerate(_TABLES)
        if "amount_cents" in _columns(conn, table)
    ]
    if not legacy_tables:
        return

    # Stable identifiers let backfill resume or restart without storing amounts.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS _lm_micros_backfill (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            table_kind INTEGER NOT NULL,
            record_id TEXT NOT NULL,
            UNIQUE(table_kind, record_id)
        )
    ''')

    for kind, table, key in legacy_tables:
        if "amount_micros" not in _columns(conn, table):
            # Nullable so unchanged v1 INSERT statements continue to work.
            conn.execute(
                f'ALTER TABLE "{table}" ADD COLUMN amount_micros INTEGER'
            )

        conn.execute(f'''
            CREATE TRIGGER IF NOT EXISTS "_lm_{table}_micros_insert"
            AFTER INSERT ON "{table}"
            BEGIN
                UPDATE "{table}"
                SET amount_micros = NEW.amount_cents * 10000
                WHERE "{key}" = NEW."{key}";
            END
        ''')
        conn.execute(f'''
            CREATE TRIGGER IF NOT EXISTS "_lm_{table}_micros_update"
            AFTER UPDATE OF amount_cents ON "{table}"
            BEGIN
                UPDATE "{table}"
                SET amount_micros = NEW.amount_cents * 10000
                WHERE "{key}" = NEW."{key}";
            END
        ''')

        # Only identities are queued. Backfill reads each row's current cents.
        # New rows are immediately populated by the INSERT triggers.
        conn.execute(f'''
            INSERT OR IGNORE INTO _lm_micros_backfill(table_kind, record_id)
            SELECT ?, "{key}" FROM "{table}" ORDER BY "{key}"
        ''', (kind,))


def backfill(conn, cursor, limit):
    if limit <= 0:
        raise ValueError("limit must be positive")

    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (_QUEUE,),
    ).fetchone()
    if exists is None:
        return {"cursor": cursor, "done": True}

    rows = conn.execute('''
        SELECT sequence, table_kind, record_id
        FROM _lm_micros_backfill
        WHERE sequence > ?
        ORDER BY sequence
        LIMIT ?
    ''', (cursor, limit + 1)).fetchall()

    next_cursor = cursor
    for sequence, kind, record_id in rows[:limit]:
        table, key = _TABLES[kind]
        conn.execute(f'''
            UPDATE "{table}"
            SET amount_micros = amount_cents * 10000
            WHERE "{key}" = ?
        ''', (record_id,))
        next_cursor = sequence

    return {"cursor": next_cursor, "done": len(rows) <= limit}


def contract(conn):
    # Rebuilds work on SQLite versions without ALTER TABLE DROP COLUMN.
    # The driver owns the surrounding transaction.
    for table, _ in _TABLES:
        conn.execute(f'DROP TRIGGER IF EXISTS "_lm_{table}_micros_insert"')
        conn.execute(f'DROP TRIGGER IF EXISTS "_lm_{table}_micros_update"')

    if "amount_cents" in _columns(conn, "orders"):
        conn.execute('''
            CREATE TABLE _lm_orders_micros_final (
                order_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL,
                amount_micros INTEGER NOT NULL
            )
        ''')
        conn.execute('''
            INSERT INTO _lm_orders_micros_final
                (order_id, revision, amount_micros)
            SELECT order_id, revision, amount_cents * 10000
            FROM orders
        ''')
        conn.execute('DROP TABLE orders')
        conn.execute('ALTER TABLE _lm_orders_micros_final RENAME TO orders')

    if "amount_cents" in _columns(conn, "payments"):
        conn.execute('''
            CREATE TABLE _lm_payments_micros_final (
                payment_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                order_revision INTEGER NOT NULL,
                amount_micros INTEGER NOT NULL
            )
        ''')
        # Each payment supplies its own immutable snapshot, independently
        # of the order's current revision or amount.
        conn.execute('''
            INSERT INTO _lm_payments_micros_final
                (payment_id, order_id, order_revision, amount_micros)
            SELECT payment_id, order_id, order_revision, amount_cents * 10000
            FROM payments
        ''')
        conn.execute('DROP TABLE payments')
        conn.execute('ALTER TABLE _lm_payments_micros_final RENAME TO payments')

    conn.execute('DROP TABLE IF EXISTS _lm_micros_backfill')

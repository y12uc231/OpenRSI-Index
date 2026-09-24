"""Reference expansion, compatibility bridge, incremental backfill, contraction."""


def expand(conn):
    for table in ("orders", "payments"):
        conn.execute("ALTER TABLE %s ADD COLUMN amount_micros INTEGER" % table)
    conn.execute("""CREATE TRIGGER orders_insert_bridge AFTER INSERT ON orders
        WHEN NEW.amount_micros IS NULL BEGIN
        UPDATE orders SET amount_micros=NEW.amount_cents*10000 WHERE order_id=NEW.order_id; END""")
    conn.execute("""CREATE TRIGGER orders_update_bridge AFTER UPDATE OF amount_cents ON orders
        BEGIN UPDATE orders SET amount_micros=NEW.amount_cents*10000 WHERE order_id=NEW.order_id; END""")
    conn.execute("""CREATE TRIGGER payments_insert_bridge AFTER INSERT ON payments
        WHEN NEW.amount_micros IS NULL BEGIN
        UPDATE payments SET amount_micros=NEW.amount_cents*10000 WHERE payment_id=NEW.payment_id; END""")


def backfill(conn, cursor, limit):
    # A cursor walks a stable union of identities, not two independent table rowids.
    rows = conn.execute("""SELECT 'orders' AS tab, order_id AS ident FROM orders
        UNION ALL SELECT 'payments', payment_id FROM payments ORDER BY tab, ident
        LIMIT ? OFFSET ?""", (limit, cursor)).fetchall()
    for row in rows:
        key = "order_id" if row["tab"] == "orders" else "payment_id"
        conn.execute("UPDATE %s SET amount_micros=amount_cents*10000 WHERE %s=? AND amount_micros IS NULL" % (row["tab"], key), (row["ident"],))
    return {"cursor": cursor + len(rows), "done": len(rows) < limit}


def contract(conn):
    # Cents remains authoritative until the retirement barrier. Reconcile before
    # removing it. This cannot undo any wrong live read or external settlement.
    for table in ("orders", "payments"):
        conn.execute("UPDATE %s SET amount_micros=amount_cents*10000" % table)
    for trigger in ("orders_insert_bridge", "orders_update_bridge", "payments_insert_bridge"):
        conn.execute("DROP TRIGGER IF EXISTS " + trigger)
    conn.execute("CREATE TABLE orders_next(order_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, amount_micros INTEGER NOT NULL)")
    conn.execute("INSERT INTO orders_next SELECT order_id,revision,amount_micros FROM orders")
    conn.execute("DROP TABLE orders")
    conn.execute("ALTER TABLE orders_next RENAME TO orders")
    conn.execute("CREATE TABLE payments_next(payment_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, order_revision INTEGER NOT NULL, amount_micros INTEGER NOT NULL)")
    conn.execute("INSERT INTO payments_next SELECT payment_id,order_id,order_revision,amount_micros FROM payments")
    conn.execute("DROP TABLE payments")
    conn.execute("ALTER TABLE payments_next RENAME TO payments")

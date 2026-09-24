"""Identity-preserving expansion, backfill, and contraction."""


def _legacy_exists(conn):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='requests'"
    ).fetchone() is not None


def _ensure_scoped(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scoped_requests (
            tenant_id TEXT NOT NULL,
            request_id TEXT NOT NULL,
            account_id TEXT NOT NULL,
            delta INTEGER NOT NULL,
            operation_id TEXT NOT NULL UNIQUE,
            PRIMARY KEY (tenant_id, request_id)
        )
    """)


def _install_view(conn, include_legacy):
    conn.execute("DROP VIEW IF EXISTS accepted_requests")
    statement = """
        CREATE VIEW accepted_requests
            (tenant_id, request_id, account_id, delta, operation_id) AS
        SELECT tenant_id, request_id, account_id, delta, operation_id
        FROM scoped_requests
    """
    if include_legacy:
        statement += """
            UNION ALL
            SELECT r.tenant_id, r.request_id, r.account_id,
                   r.delta, r.operation_id
            FROM requests AS r
            WHERE NOT EXISTS (
                SELECT 1 FROM scoped_requests AS s
                WHERE s.tenant_id = r.tenant_id
                  AND s.request_id = r.request_id
            )
        """
    conn.execute(statement)


def expand(conn):
    _ensure_scoped(conn)
    _install_view(conn, _legacy_exists(conn))


def backfill(conn, cursor, limit):
    if not _legacy_exists(conn):
        return {"cursor": cursor, "done": True}

    if cursor is None:
        rows = conn.execute("""
            SELECT tenant_id, request_id, account_id, delta, operation_id
            FROM requests ORDER BY request_id LIMIT ?
        """, (limit,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT tenant_id, request_id, account_id, delta, operation_id
            FROM requests WHERE request_id > ?
            ORDER BY request_id LIMIT ?
        """, (cursor, limit)).fetchall()

    for row in rows:
        values = tuple(row)
        conn.execute("""
            INSERT INTO scoped_requests
                (tenant_id, request_id, account_id, delta, operation_id)
            SELECT ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM scoped_requests
                WHERE tenant_id = ? AND request_id = ?
            )
        """, values + (values[0], values[1]))

    if not rows:
        return {"cursor": cursor, "done": True}

    next_cursor = rows[-1][1]
    remaining = conn.execute(
        "SELECT 1 FROM requests WHERE request_id > ? LIMIT 1",
        (next_cursor,)
    ).fetchone()
    return {"cursor": next_cursor, "done": remaining is None}


def contract(conn):
    _ensure_scoped(conn)
    legacy_exists = _legacy_exists(conn)
    if legacy_exists:
        # Reconcile legacy arrivals behind any previous backfill cursor.
        conn.execute("""
            INSERT INTO scoped_requests
                (tenant_id, request_id, account_id, delta, operation_id)
            SELECT r.tenant_id, r.request_id, r.account_id,
                   r.delta, r.operation_id
            FROM requests AS r
            WHERE NOT EXISTS (
                SELECT 1 FROM scoped_requests AS s
                WHERE s.tenant_id = r.tenant_id
                  AND s.request_id = r.request_id
            )
        """)
    _install_view(conn, False)
    if legacy_exists:
        conn.execute("DROP TABLE requests")

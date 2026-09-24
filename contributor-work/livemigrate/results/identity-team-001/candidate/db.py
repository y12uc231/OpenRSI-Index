"""Identity-preserving migration from global to tenant-scoped requests."""


def _has_legacy(conn):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='requests'"
    ).fetchone() is not None


def _ensure_store(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scoped_requests ("
        "tenant_id TEXT NOT NULL, "
        "request_id TEXT NOT NULL, "
        "account_id TEXT NOT NULL, "
        "delta INTEGER NOT NULL, "
        "operation_id TEXT NOT NULL UNIQUE, "
        "PRIMARY KEY (tenant_id, request_id))"
    )


def _install_view(conn, include_legacy):
    conn.execute("DROP VIEW IF EXISTS accepted_requests")
    query = (
        "CREATE VIEW accepted_requests AS "
        "SELECT tenant_id, request_id, account_id, delta, operation_id "
        "FROM scoped_requests"
    )
    if include_legacy:
        query += (
            " UNION ALL "
            "SELECT r.tenant_id, r.request_id, r.account_id, r.delta, r.operation_id "
            "FROM requests AS r "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM scoped_requests AS s "
            "WHERE s.tenant_id=r.tenant_id AND s.request_id=r.request_id)"
        )
    conn.execute(query)


def expand(conn):
    _ensure_store(conn)
    _install_view(conn, _has_legacy(conn))


def backfill(conn, cursor, limit):
    expand(conn)
    if not _has_legacy(conn):
        return {"cursor": cursor, "done": True}

    query = (
        "SELECT tenant_id, request_id, account_id, delta, operation_id "
        "FROM requests"
    )
    if cursor is None:
        params = (limit + 1,)
    else:
        query += " WHERE request_id > ?"
        params = (cursor, limit + 1)
    query += " ORDER BY request_id LIMIT ?"
    rows = conn.execute(query, params).fetchall()
    batch = rows[:limit]

    for row in batch:
        tenant, request_id, account, delta, operation = (
            row[0], row[1], row[2], row[3], row[4]
        )
        conn.execute(
            "INSERT INTO scoped_requests "
            "(tenant_id, request_id, account_id, delta, operation_id) "
            "SELECT ?, ?, ?, ?, ? WHERE NOT EXISTS ("
            "SELECT 1 FROM scoped_requests "
            "WHERE tenant_id=? AND request_id=?)",
            (tenant, request_id, account, delta, operation, tenant, request_id),
        )

    return {
        "cursor": batch[-1][1] if batch else cursor,
        "done": len(rows) <= limit,
    }


def contract(conn):
    _ensure_store(conn)
    has_legacy = _has_legacy(conn)
    if has_legacy:
        # Include legacy keys inserted behind any previous backfill cursor.
        # Match both identity fields so scoped key reuse remains valid.
        conn.execute(
            "INSERT INTO scoped_requests "
            "(tenant_id, request_id, account_id, delta, operation_id) "
            "SELECT r.tenant_id, r.request_id, r.account_id, r.delta, r.operation_id "
            "FROM requests AS r "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM scoped_requests AS s "
            "WHERE s.tenant_id=r.tenant_id AND s.request_id=r.request_id)"
        )

    _install_view(conn, False)
    if has_legacy:
        conn.execute("DROP TABLE requests")

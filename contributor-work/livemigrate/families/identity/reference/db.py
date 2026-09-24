"""One valid layout; scoped table names are not part of the task contract."""


def expand(conn):
    conn.execute("""CREATE TABLE scoped_requests(tenant_id TEXT NOT NULL, request_id TEXT NOT NULL,
        account_id TEXT NOT NULL,delta INTEGER NOT NULL,operation_id TEXT NOT NULL UNIQUE,
        PRIMARY KEY(tenant_id,request_id))""")
    conn.execute("""CREATE VIEW accepted_requests AS
        SELECT tenant_id,request_id,account_id,delta,operation_id FROM scoped_requests
        UNION ALL SELECT tenant_id,request_id,account_id,delta,operation_id FROM requests r
        WHERE NOT EXISTS(SELECT 1 FROM scoped_requests s WHERE s.tenant_id=r.tenant_id AND s.request_id=r.request_id)""")


def _import(conn, row):
    old = conn.execute("SELECT * FROM scoped_requests WHERE tenant_id=? AND request_id=?", (row["tenant_id"], row["request_id"])).fetchone()
    if old is None:
        conn.execute("INSERT INTO scoped_requests VALUES(?,?,?,?,?)", (row["tenant_id"], row["request_id"], row["account_id"], row["delta"], row["operation_id"]))
    elif any(old[key] != row[key] for key in ("account_id", "delta", "operation_id")):
        raise ValueError("immutable imported request disagreement")


def backfill(conn, cursor, limit):
    rows = conn.execute("SELECT * FROM requests WHERE ? IS NULL OR request_id>? ORDER BY request_id LIMIT ?", (cursor, cursor, limit)).fetchall()
    for row in rows:
        _import(conn, row)
    return {"cursor": rows[-1]["request_id"] if rows else cursor, "done": len(rows) < limit}


def contract(conn):
    for row in conn.execute("SELECT * FROM requests ORDER BY request_id").fetchall():
        _import(conn, row)
    conn.execute("DROP VIEW accepted_requests")
    conn.execute("DROP TABLE requests")
    conn.execute("CREATE VIEW accepted_requests AS SELECT tenant_id,request_id,account_id,delta,operation_id FROM scoped_requests")

"""Credit admissions with permanent operation identities."""
import json


def handle(conn, request, phase):
    tenant = request["tenant_id"]
    account = request["account_id"]
    if request["op"] == "balance":
        balance = conn.execute(
            "SELECT balance FROM accounts WHERE tenant_id=? AND account_id=?",
            (tenant, account)
        ).fetchone()[0]
        return {"ok": True, "tenant_id": tenant,
                "account_id": account, "balance": balance}

    request_id = request["request_id"]
    delta = request["delta"]
    if type(delta) is not int or delta <= 0:
        return {"ok": False, "error": "invalid_request"}

    if phase == "overlap":
        # Both writer generations use the legacy global admission gate.
        old = conn.execute("""
            SELECT tenant_id, account_id, delta, operation_id
            FROM requests WHERE request_id=?
        """, (request_id,)).fetchone()
    else:
        # Include legacy admissions that backfill has not copied yet.
        old = conn.execute("""
            SELECT tenant_id, account_id, delta, operation_id
            FROM accepted_requests WHERE tenant_id=? AND request_id=?
        """, (tenant, request_id)).fetchone()

    if old is not None:
        if old[0] != tenant or old[1] != account or old[2] != delta:
            return {"ok": False, "error": "idempotency_conflict"}
        return {"ok": True, "operation_id": old[3]}

    identity = (["legacy", request_id] if phase == "overlap"
                else ["scoped", tenant, request_id])
    operation = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))

    if phase == "overlap":
        conn.execute("""
            INSERT INTO requests
                (request_id, tenant_id, account_id, delta, operation_id)
            VALUES (?, ?, ?, ?, ?)
        """, (request_id, tenant, account, delta, operation))

    conn.execute("""
        INSERT INTO scoped_requests
            (tenant_id, request_id, account_id, delta, operation_id)
        VALUES (?, ?, ?, ?, ?)
    """, (tenant, request_id, account, delta, operation))
    conn.execute("""
        UPDATE accounts SET balance=balance+?
        WHERE tenant_id=? AND account_id=?
    """, (delta, tenant, account))

    payload = {"tenant_id": tenant, "request_id": request_id,
               "account_id": account, "delta": delta,
               "operation_id": operation}
    conn.execute("""
        INSERT INTO outbox (event_id, operation_id, version, payload)
        VALUES (?, ?, 1, ?)
    """, (operation, operation,
          json.dumps(payload, ensure_ascii=False, sort_keys=True)))
    return {"ok": True, "operation_id": operation}

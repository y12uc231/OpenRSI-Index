"""Credit API preserving accepted identities across the migration phases."""
import json


def _retry_response(row, tenant, account, delta):
    if row[0] != tenant or row[1] != account or row[2] != delta:
        return {"ok": False, "error": "idempotency_conflict"}
    return {"ok": True, "operation_id": row[3]}


def handle(conn, request, phase):
    if not isinstance(request, dict) or phase not in ("overlap", "retired", "complete"):
        return {"ok": False, "error": "invalid_request"}

    tenant = request.get("tenant_id")
    account = request.get("account_id")
    if type(tenant) is not str or type(account) is not str:
        return {"ok": False, "error": "invalid_request"}

    if request.get("op") == "balance":
        row = conn.execute(
            "SELECT balance FROM accounts WHERE tenant_id=? AND account_id=?",
            (tenant, account),
        ).fetchone()
        return {
            "ok": True,
            "tenant_id": tenant,
            "account_id": account,
            "balance": int(row[0]),
        }

    if request.get("op") != "credit":
        return {"ok": False, "error": "invalid_request"}

    request_id = request.get("request_id")
    delta = request.get("delta")
    if type(request_id) is not str or type(delta) is not int or delta <= 0:
        return {"ok": False, "error": "invalid_request"}

    if phase == "overlap":
        existing = conn.execute(
            "SELECT tenant_id,account_id,delta,operation_id "
            "FROM requests WHERE request_id=?",
            (request_id,),
        ).fetchone()
        if existing is not None:
            return _retry_response(existing, tenant, account, delta)
        operation_id = json.dumps(
            ["legacy", request_id], ensure_ascii=False, separators=(",", ":")
        )
        insert_sql = (
            "INSERT INTO requests "
            "(request_id,tenant_id,account_id,delta,operation_id) "
            "VALUES(?,?,?,?,?)"
        )
    else:
        existing = conn.execute(
            "SELECT tenant_id,account_id,delta,operation_id "
            "FROM accepted_requests WHERE tenant_id=? AND request_id=?",
            (tenant, request_id),
        ).fetchone()
        if existing is not None:
            return _retry_response(existing, tenant, account, delta)
        operation_id = json.dumps(
            ["scoped", tenant, request_id],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        insert_sql = (
            "INSERT INTO scoped_requests "
            "(request_id,tenant_id,account_id,delta,operation_id) "
            "VALUES(?,?,?,?,?)"
        )

    payload = json.dumps(
        {
            "tenant_id": tenant,
            "request_id": request_id,
            "account_id": account,
            "delta": delta,
            "operation_id": operation_id,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    conn.execute(insert_sql, (request_id, tenant, account, delta, operation_id))
    conn.execute(
        "UPDATE accounts SET balance=balance+? WHERE tenant_id=? AND account_id=?",
        (delta, tenant, account),
    )
    conn.execute(
        "INSERT INTO outbox (event_id,operation_id,version,payload) VALUES(?,?,1,?)",
        (operation_id, operation_id, payload),
    )
    return {"ok": True, "operation_id": operation_id}

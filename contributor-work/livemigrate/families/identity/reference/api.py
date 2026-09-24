"""Reference global-to-scoped identity admission and custom v3 event layout."""
import json


def handle(conn, request, phase):
    tenant, account = request["tenant_id"], request["account_id"]
    if request["op"] == "balance":
        value = conn.execute("SELECT balance FROM accounts WHERE tenant_id=? AND account_id=?", (tenant, account)).fetchone()[0]
        return {"ok": True, "tenant_id": tenant, "account_id": account, "balance": value}
    key = request["request_id"]
    if phase == "overlap":
        old = conn.execute("SELECT * FROM requests WHERE request_id=?", (key,)).fetchone()
    else:
        old = conn.execute("SELECT * FROM scoped_requests WHERE tenant_id=? AND request_id=?", (tenant, key)).fetchone()
        if old is None and phase == "retired":
            old = conn.execute("SELECT * FROM requests WHERE tenant_id=? AND request_id=?", (tenant, key)).fetchone()
    if old is not None:
        if old["tenant_id"] != tenant or old["account_id"] != account or old["delta"] != request["delta"]:
            return {"ok": False, "error": "idempotency_conflict"}
        return {"ok": True, "operation_id": old["operation_id"]}
    operation = json.dumps(["legacy", key] if phase == "overlap" else ["tenant", tenant, key], ensure_ascii=False, separators=(",", ":"))
    if phase == "overlap":
        conn.execute("INSERT INTO requests VALUES(?,?,?,?,?)", (key, tenant, account, request["delta"], operation))
    conn.execute("INSERT INTO scoped_requests VALUES(?,?,?,?,?)", (tenant, key, account, request["delta"], operation))
    conn.execute("UPDATE accounts SET balance=balance+? WHERE tenant_id=? AND account_id=?", (request["delta"], tenant, account))
    if phase == "overlap":
        payload = {"tenant_id": tenant, "request_id": key, "account_id": account, "delta": request["delta"], "operation_id": operation}
        version = 2
    else:
        payload = {"receipt": operation, "credit": {"tenant": tenant, "request": key, "account": account, "units": request["delta"]}}
        version = 3
    conn.execute("INSERT INTO outbox VALUES(?,?,?,?)", (operation, operation, version, json.dumps(payload, ensure_ascii=False, sort_keys=True)))
    return {"ok": True, "operation_id": operation}

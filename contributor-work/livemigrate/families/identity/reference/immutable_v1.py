"""Immutable legacy credit API and consumer; not candidate-owned."""
import json


def handle(conn, request, phase=None):
    tenant, account = request["tenant_id"], request["account_id"]
    if request["op"] == "balance":
        balance = conn.execute("SELECT balance FROM accounts WHERE tenant_id=? AND account_id=?", (tenant, account)).fetchone()[0]
        return {"ok": True, "tenant_id": tenant, "account_id": account, "balance": balance}
    old = conn.execute("SELECT * FROM requests WHERE request_id=?", (request["request_id"],)).fetchone()
    if old is not None:
        if old["tenant_id"] != tenant or old["account_id"] != account or old["delta"] != request["delta"]:
            return {"ok": False, "error": "idempotency_conflict"}
        return {"ok": True, "operation_id": old["operation_id"]}
    operation = json.dumps(["legacy", request["request_id"]], ensure_ascii=False, separators=(",", ":"))
    conn.execute("INSERT INTO requests VALUES(?,?,?,?,?)", (request["request_id"], tenant, account, request["delta"], operation))
    conn.execute("UPDATE accounts SET balance=balance+? WHERE tenant_id=? AND account_id=?", (request["delta"], tenant, account))
    payload = {"tenant_id": tenant, "request_id": request["request_id"], "account_id": account, "delta": request["delta"], "operation_id": operation}
    conn.execute("INSERT INTO outbox VALUES(?,?,1,?)", (operation, operation, json.dumps(payload, ensure_ascii=False, sort_keys=True)))
    return {"ok": True, "operation_id": operation}


def consume(conn, event):
    result = dict(event["payload"])
    result["idempotency_key"] = result["operation_id"]
    return result

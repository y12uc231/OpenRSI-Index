"""Consume immutable receipts or resolve references by permanent operation ID."""


def consume(conn, event):
    operation_id = event["operation_id"]
    if not isinstance(operation_id, str) or not operation_id:
        raise ValueError("Expected a nonempty permanent operation ID")

    payload = event["payload"]
    fields = ("tenant_id", "request_id", "account_id", "delta")
    if isinstance(payload, dict):
        if "operation_id" in payload and payload["operation_id"] != operation_id:
            raise ValueError("Event and payload operation IDs disagree")

    if isinstance(payload, dict) and all(field in payload for field in fields):
        tenant_id = payload["tenant_id"]
        request_id = payload["request_id"]
        account_id = payload["account_id"]
        delta = payload["delta"]
    else:
        rows = conn.execute(
            "SELECT tenant_id, request_id, account_id, delta "
            "FROM accepted_requests WHERE operation_id = ?",
            (operation_id,),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("Operation reference must identify exactly one accepted record")
        tenant_id, request_id, account_id, delta = rows[0]

    if not all(isinstance(value, str) for value in (tenant_id, request_id, account_id)):
        raise ValueError("Receipt identity fields must be strings")
    if type(delta) is not int or delta <= 0:
        raise ValueError("Receipt delta must be a positive integer")

    return {
        "idempotency_key": operation_id,
        "operation_id": operation_id,
        "tenant_id": tenant_id,
        "request_id": request_id,
        "account_id": account_id,
        "delta": delta,
    }

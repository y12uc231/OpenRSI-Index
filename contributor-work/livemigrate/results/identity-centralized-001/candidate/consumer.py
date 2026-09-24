"""Deliver immutable event instructions without database lookups."""


def consume(conn, event):
    # Every writer emits a complete version-1 payload.
    payload = event["payload"]
    operation = payload["operation_id"]
    return {
        "idempotency_key": operation,
        "operation_id": operation,
        "tenant_id": payload["tenant_id"],
        "request_id": payload["request_id"],
        "account_id": payload["account_id"],
        "delta": payload["delta"],
    }

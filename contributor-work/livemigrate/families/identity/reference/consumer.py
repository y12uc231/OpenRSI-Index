"""Read immutable event identity, including legacy events after contraction."""


def consume(conn, event):
    payload = event["payload"]
    if event["version"] in (1, 2):
        result = dict(payload)
    else:
        credit = payload["credit"]
        result = {"operation_id": payload["receipt"], "tenant_id": credit["tenant"], "request_id": credit["request"], "account_id": credit["account"], "delta": credit["units"]}
    result["idempotency_key"] = result["operation_id"]
    return result

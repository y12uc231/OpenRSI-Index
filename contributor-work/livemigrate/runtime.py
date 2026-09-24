"""Deterministic live-migration evaluator with an external request/effect ledger.

The default in-process invoker is for trusted references and synthetic tests.
For generated candidate code, pass an isolated RPC invoker. Neither the input-
derived expected ledger nor the settlement sink is stored in candidate SQLite.
"""
import argparse
import copy
import importlib.util
import json
import pathlib
import sqlite3
import tempfile
import uuid

import scenarios

HERE = pathlib.Path(__file__).resolve().parent
SCHEMA = """
CREATE TABLE orders(order_id TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL, revision INTEGER NOT NULL);
CREATE TABLE payments(payment_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, order_revision INTEGER NOT NULL, amount_cents INTEGER NOT NULL);
CREATE TABLE outbox(event_id TEXT PRIMARY KEY, payment_id TEXT NOT NULL UNIQUE, version INTEGER NOT NULL, payload TEXT NOT NULL);
"""


def _module(path):
    spec = importlib.util.spec_from_file_location("livemigrate_" + uuid.uuid4().hex, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _readonly(action, arg1, arg2, db_name, trigger):
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY


def trusted_invoker(candidate_dir):
    """Only use for code trusted by the harness operator; not a Python sandbox."""
    modules = {role: _module(pathlib.Path(candidate_dir) / (role + ".py")) for role in ("db", "api", "consumer")}

    def invoke(role, function, conn, *args):
        if role == "consumer":
            conn.set_authorizer(_readonly)
            try:
                return getattr(modules[role], function)(conn, *copy.deepcopy(args))
            finally:
                # Python 3.9 linked against recent SQLite can retain a denial
                # after set_authorizer(None); an explicit allow callback resets.
                conn.set_authorizer(lambda *unused: sqlite3.SQLITE_OK)
        with conn:
            return getattr(modules[role], function)(conn, *copy.deepcopy(args))
    return invoke


def execute(candidate_dir, scenario, invoke=None):
    """Run one logical traffic trace; return JSON-safe diagnostic components.

    External invokers receive no open host transaction and must commit each
    callback before returning. They receive only the working SQLite connection
    path and the callback inputs, never the oracle's ledger or settlement sink.
    """
    scenario = copy.deepcopy(scenario)
    expected_orders = {row["order_id"]: {"revision": row["revision"], "amount_micros": row["amount_cents"] * 10000} for row in scenario["initial_orders"]}
    expected_payments = {}
    outbox_seen = {}
    sink = {}  # Physical external effects, retained despite DB repair/rollback.
    trace_errors = []
    static_errors = []
    delivery_count = 0
    callback_count = 0
    cursor = 0
    completed_steps = 0
    expanded = False
    contracted = False
    legacy = _module(HERE / "reference" / "immutable_v1.py")

    def error(code, step, **details):
        trace_errors.append(dict(code=code, step=step, **details))

    try:
        call = invoke if invoke is not None else trusted_invoker(candidate_dir)
    except Exception as exc:
        return {"name": scenario["name"], "status": "candidate_invalid", "score": None, "passed": False, "static": {"passed": False, "violations": [{"code": "candidate_load", "error_type": type(exc).__name__}]}, "trace": {"passed": False, "violations": []}, "completion": {"passed": False, "completed_steps": 0, "total_steps": len(scenario["steps"])}}

    with tempfile.TemporaryDirectory(prefix="livemigrate-") as temp:
        conn = sqlite3.connect(str(pathlib.Path(temp) / "state.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO orders(order_id,amount_cents,revision) VALUES(?,?,?)", [(r["order_id"], r["amount_cents"], r["revision"]) for r in scenario["initial_orders"]])
        conn.commit()

        def candidate(role, function, *args):
            nonlocal callback_count
            conn.commit()
            callback_count += 1
            result = call(role, function, conn, *copy.deepcopy(args))
            conn.row_factory = sqlite3.Row
            return result

        def check_outbox(step):
            """Check atomic event creation and append-only history at every step."""
            try:
                rows = {row["payment_id"]: dict(row) for row in conn.execute("SELECT event_id,payment_id,version,payload FROM outbox")}
            except sqlite3.Error as exc:
                error("outbox_unreadable", step, error_type=type(exc).__name__)
                return
            for payment, previous in outbox_seen.items():
                if rows.get(payment) != previous:
                    error("outbox_history_changed", step, payment_id=payment)
            for payment, row in rows.items():
                if payment not in expected_payments:
                    error("unaccepted_payment_event", step, payment_id=payment)
                    continue
                expected = expected_payments[payment]
                try:
                    payload = json.loads(row["payload"])
                    raw_amount = payload["amount_cents"] if row["version"] == 1 else payload["amount_micros"]
                    amount = raw_amount * 10000 if row["version"] == 1 else raw_amount
                    if type(raw_amount) is not int or type(payload["order_revision"]) is not int or row["event_id"] != payment or payload["payment_id"] != payment or payload["order_id"] != expected["order_id"] or payload["order_revision"] != expected["order_revision"] or amount != expected["amount_micros"] or row["version"] not in (1, 2):
                        error("incorrect_payment_event", step, payment_id=payment)
                except (KeyError, TypeError, ValueError):
                    error("malformed_payment_event", step, payment_id=payment)
                if payment not in outbox_seen:
                    outbox_seen[payment] = row
            for payment in expected_payments:
                if payment not in rows:
                    error("missing_payment_event", step, payment_id=payment)

        def check_live_tables(step):
            # During overlap cents is the legacy-visible logical value. An
            # unused micros shadow can be null or stale; incorrect externally
            # observable reads/events are checked separately. After contraction
            # micros is authoritative.
            for table, key, expected_rows in (("orders", "order_id", expected_orders), ("payments", "payment_id", expected_payments)):
                try:
                    columns = {r["name"] for r in conn.execute("PRAGMA table_info(" + table + ")")}
                    rows = {row[key]: dict(row) for row in conn.execute("SELECT * FROM " + table)}
                    if set(rows) != set(expected_rows):
                        error("incorrect_live_identities", step, table=table)
                    for identity, expected in expected_rows.items():
                        row = rows.get(identity, {})
                        amount = row.get("amount_cents") * 10000 if "amount_cents" in columns and type(row.get("amount_cents")) is int else row.get("amount_micros")
                        actual = dict(row, amount_micros=amount)
                        if any(actual.get(field) != value for field, value in expected.items()):
                            error("incorrect_live_row", step, table=table, identity=identity)
                except (sqlite3.Error, TypeError) as exc:
                    error("live_table_unreadable", step, table=table, error_type=type(exc).__name__)

        def expected_request(request, actor):
            order_id, op = request["order_id"], request["op"]
            order = expected_orders.get(order_id)
            if op == "get":
                field = "amount_cents" if actor == 1 else "amount_micros"
                return {"ok": True, "order_id": order_id, "revision": order["revision"], field: order["amount_micros"] // 10000 if actor == 1 else order["amount_micros"]}
            if op == "pay" and request["payment_id"] in expected_payments:
                payment = expected_payments[request["payment_id"]]
                if payment["order_id"] != order_id or payment["order_revision"] != request["expected_revision"]:
                    return {"ok": False, "error": "idempotency_conflict"}
                return {"ok": True, "payment_id": request["payment_id"]}
            revision = 0 if order is None else order["revision"]
            if request["expected_revision"] != revision:
                return {"ok": False, "error": "revision_conflict"}
            if op == "put":
                amount = request["amount_cents"] * 10000 if actor == 1 else request["amount_micros"]
                expected_orders[order_id] = {"revision": revision + 1, "amount_micros": amount}
                return {"ok": True, "revision": revision + 1}
            if op == "pay":
                expected_payments[request["payment_id"]] = {"order_id": order_id, "order_revision": revision, "amount_micros": order["amount_micros"]}
                return {"ok": True, "payment_id": request["payment_id"]}
            raise ValueError("unknown oracle operation")

        def deliver(payment_id, version, step):
            nonlocal delivery_count
            row = conn.execute("SELECT * FROM outbox WHERE payment_id=?", (payment_id,)).fetchone()
            if row is None:
                error("delivery_missing_event", step, payment_id=payment_id)
                return
            event = dict(row)
            event["payload"] = json.loads(event["payload"])
            if version == 1:
                result = legacy.consume(conn, copy.deepcopy(event))
            else:
                result = candidate("consumer", "consume", event)
            delivery_count += 1
            if not isinstance(result, dict) or not isinstance(result.get("idempotency_key"), str) or not result["idempotency_key"] or type(result.get("amount_micros")) is not int or not isinstance(result.get("payment_id"), str):
                error("malformed_settlement", step, payment_id=payment_id)
                return
            expected = expected_payments.get(payment_id)
            if expected is None or result["payment_id"] != payment_id or result["amount_micros"] != expected["amount_micros"]:
                error("incorrect_settlement_attempt", step, payment_id=payment_id)
            key = result["idempotency_key"]
            if key != payment_id:
                error("incorrect_idempotency_key", step, payment_id=payment_id)
            charge = {"payment_id": result["payment_id"], "amount_micros": result["amount_micros"]}
            if key in sink:
                if sink[key] != charge:
                    error("idempotency_key_conflict", step, payment_id=payment_id)
            else:
                sink[key] = charge

        try:
            for index, step in enumerate(scenario["steps"]):
                try:
                    kind = step["kind"]
                    if kind == "expand":
                        candidate("db", "expand")
                        expanded = True
                    elif kind == "backfill":
                        result = candidate("db", "backfill", cursor, step["limit"])
                        if not isinstance(result, dict) or type(result.get("cursor")) is not int or type(result.get("done")) is not bool or result["cursor"] < cursor or (result["cursor"] == cursor and not result["done"]):
                            raise ValueError("invalid backfill progress")
                        cursor = result["cursor"]
                    elif kind == "backfill_all":
                        cursor = 0
                        for attempt in range(64):
                            result = candidate("db", "backfill", cursor, step["limit"])
                            if not isinstance(result, dict) or type(result.get("cursor")) is not int or type(result.get("done")) is not bool or result["cursor"] < cursor or (result["cursor"] == cursor and not result["done"]):
                                raise ValueError("invalid backfill progress")
                            cursor = result["cursor"]
                            if result["done"]:
                                break
                        else:
                            raise ValueError("backfill did not finish")
                    elif kind == "request":
                        request = step["request"]
                        expected = expected_request(request, step["actor"])
                        if step["actor"] == 1:
                            with conn:
                                result = legacy.handle(conn, copy.deepcopy(request))
                        else:
                            result = candidate("api", "handle", request, step["phase"])
                        if not isinstance(result, dict) or any(type(result.get(key)) is not type(value) or result.get(key) != value for key, value in expected.items()):
                            error("incorrect_request_result", index, actor=step["actor"], operation=request["op"], order_id=request["order_id"], expected=expected, observed=result if isinstance(result, (dict, list, str, int, bool, type(None))) else type(result).__name__)
                    elif kind == "deliver":
                        for repeat in range(step.get("repeats", 1)):
                            deliver(step["payment_id"], step["consumer"], index)
                    elif kind == "drain":
                        # Every pending payment is delivered again, including
                        # those whose earlier external charge ACK was lost.
                        for payment in sorted(expected_payments):
                            deliver(payment, 2, index)
                    elif kind == "contract":
                        candidate("db", "contract")
                        contracted = True
                    else:
                        raise ValueError("unknown schedule action")
                    completed_steps += 1
                except Exception as exc:
                    if getattr(exc, "infrastructure_error", False):
                        raise
                    conn.rollback()
                    error("callback_error", index, action=step["kind"], error_type=type(exc).__name__)
                check_outbox(index)
                check_live_tables(index)

            for table, key, expected_rows in (("orders", "order_id", expected_orders), ("payments", "payment_id", expected_payments)):
                try:
                    columns = {r["name"] for r in conn.execute("PRAGMA table_info(" + table + ")")}
                    if "amount_micros" not in columns or "amount_cents" in columns:
                        static_errors.append({"code": "incomplete_schema", "table": table})
                    rows = {row[key]: dict(row) for row in conn.execute("SELECT * FROM " + table)}
                    if set(rows) != set(expected_rows):
                        static_errors.append({"code": "incorrect_final_identities", "table": table})
                    for identity, expected in expected_rows.items():
                        actual = rows.get(identity, {})
                        if any(actual.get(field) != value for field, value in expected.items()):
                            static_errors.append({"code": "incorrect_final_row", "table": table, "identity": identity})
                except sqlite3.Error as exc:
                    static_errors.append({"code": "final_table_unreadable", "table": table, "error_type": type(exc).__name__})
            for payment, expected in expected_payments.items():
                effects = [effect for effect in sink.values() if effect["payment_id"] == payment]
                if len(effects) != 1 or effects[0]["amount_micros"] != expected["amount_micros"]:
                    error("incorrect_physical_effects", "final", payment_id=payment, effect_count=len(effects))
            if any(effect["payment_id"] not in expected_payments for effect in sink.values()):
                error("unaccepted_physical_effect", "final")
        finally:
            conn.close()

    completion = {"passed": expanded and contracted and completed_steps == len(scenario["steps"]), "expanded": expanded, "contracted": contracted, "completed_steps": completed_steps, "total_steps": len(scenario["steps"]), "candidate_callbacks": callback_count, "deliveries": delivery_count}
    invalid = any(item["code"] == "callback_error" for item in trace_errors)
    passed = not static_errors and not trace_errors and completion["passed"]
    return {"name": scenario["name"], "status": "candidate_invalid" if invalid else "scored", "score": None if invalid else float(passed), "passed": passed, "static": {"passed": not static_errors, "violations": static_errors}, "trace": {"passed": not trace_errors, "violations": trace_errors, "accepted_payments": len(expected_payments), "physical_effects": len(sink)}, "completion": completion}


def run_suite(candidate_dir, suite_name, invoke=None, invoke_factory=None):
    results = []
    for scenario in scenarios.suite(suite_name):
        if invoke_factory is None:
            results.append(execute(candidate_dir, scenario, invoke=invoke))
        else:
            with invoke_factory(candidate_dir) as invoke:
                results.append(execute(candidate_dir, scenario, invoke=invoke))
    passed = sum(result["passed"] for result in results)
    invalid = any(result["status"] == "candidate_invalid" for result in results)
    return {"suite": suite_name, "status": "candidate_invalid" if invalid else "scored", "cases": results, "passed": passed, "total": len(results), "score": None if invalid else passed / len(results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--suite", choices=("public", "heldout", "all"), default="public")
    args = parser.parse_args()
    print(json.dumps(run_suite(args.candidate, args.suite), sort_keys=True))


if __name__ == "__main__":
    main()

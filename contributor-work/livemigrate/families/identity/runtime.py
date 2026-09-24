"""Draft identity-migration evaluator. No model outcomes were used to author it.

Infrastructure architecture adapted from contributor-work/livemigrate/runtime.py
in the personal OpenRSI-Index checkout: transaction dispatch, immutable trace
errors, external effect sink, and candidate-invalid classification. The identity
oracle and workloads are separately implemented for this family.
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
CREATE TABLE accounts(tenant_id TEXT NOT NULL,account_id TEXT NOT NULL,balance INTEGER NOT NULL,PRIMARY KEY(tenant_id,account_id));
CREATE TABLE requests(request_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,account_id TEXT NOT NULL,delta INTEGER NOT NULL,operation_id TEXT NOT NULL UNIQUE);
CREATE TABLE outbox(event_id TEXT PRIMARY KEY,operation_id TEXT NOT NULL UNIQUE,version INTEGER NOT NULL,payload TEXT NOT NULL);
"""


def _module(path):
    spec = importlib.util.spec_from_file_location("identity_" + uuid.uuid4().hex, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def trusted_invoker(candidate_dir):
    """Trusted references/tests only; generated code needs isolated dispatch."""
    modules = {role: _module(pathlib.Path(candidate_dir) / (role + ".py")) for role in ("db", "api", "consumer")}
    def invoke(role, function, conn, *args):
        if role == "consumer":
            allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
            conn.set_authorizer(lambda action, *unused: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
            try:
                return getattr(modules[role], function)(conn, *copy.deepcopy(args))
            finally:
                conn.set_authorizer(lambda *unused: sqlite3.SQLITE_OK)
        with conn:
            return getattr(modules[role], function)(conn, *copy.deepcopy(args))
    return invoke


def _same_scalars(actual, expected):
    return isinstance(actual, dict) and all(type(actual.get(k)) is type(v) and actual[k] == v for k, v in expected.items())


def execute(candidate_dir, scenario, invoke=None):
    scenario = copy.deepcopy(scenario)
    balances = {(row["tenant_id"], row["account_id"]): row["balance"] for row in scenario["accounts"]}
    accepted = {}
    global_keys = {}
    sink = {}
    outbox_seen = {}
    trace_errors = []
    static_errors = []
    expanded = contracted = False
    completed = callbacks = deliveries = 0
    cursor = None
    legacy = _module(HERE / "reference" / "immutable_v1.py")

    def error(code, step, **details):
        trace_errors.append(dict(code=code, step=step, **details))

    try:
        call = invoke if invoke is not None else trusted_invoker(candidate_dir)
    except Exception as exc:
        return {"name": scenario["name"], "status": "candidate_invalid", "score": None, "passed": False,
                "static": {"passed": False, "violations": [{"code": "candidate_load", "error_type": type(exc).__name__}]},
                "trace": {"passed": False, "violations": []}, "completion": {"passed": False, "completed_steps": 0, "total_steps": len(scenario["steps"])}}

    with tempfile.TemporaryDirectory(prefix="identity-migrate-") as directory:
        conn = sqlite3.connect(str(pathlib.Path(directory) / "state.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO accounts VALUES(?,?,?)", [(t, a, b) for (t, a), b in balances.items()])
        conn.commit()

        def candidate(role, function, *args):
            nonlocal callbacks
            conn.commit()
            callbacks += 1
            result = call(role, function, conn, *copy.deepcopy(args))
            conn.row_factory = sqlite3.Row
            return result

        def bounded_rows(query):
            ticks = [0]
            def progress():
                ticks[0] += 1
                return int(ticks[0] > 100)
            conn.set_progress_handler(progress, 10000)
            try:
                rows = conn.execute(query + " LIMIT 10001").fetchall()
                if len(rows) > 10000:
                    raise ValueError("audit row limit exceeded")
                return [dict(row) for row in rows]
            finally:
                conn.set_progress_handler(None, 0)

        def ledger_rows():
            table = "accepted_requests" if expanded else "requests"
            return bounded_rows("SELECT tenant_id,request_id,account_id,delta,operation_id FROM " + table)

        def current_state_errors():
            failures = []
            try:
                rows = bounded_rows("SELECT tenant_id,account_id,balance FROM accounts")
                actual = {(row["tenant_id"], row["account_id"]): row["balance"] for row in rows}
                if len(rows) != len(actual) or actual != balances or any(type(row["balance"]) is not int for row in rows):
                    failures.append({"code": "incorrect_balances"})
            except (sqlite3.Error, TypeError, ValueError) as exc:
                failures.append({"code": "accounts_unreadable", "error_type": type(exc).__name__})
            try:
                rows = ledger_rows()
                actual = {(row["tenant_id"], row["request_id"]): row for row in rows}
                if len(rows) != len(actual):
                    failures.append({"code": "duplicate_ledger_rows"})
                if set(actual) != set(accepted):
                    failures.append({"code": "incorrect_ledger_identities"})
                ids = [row["operation_id"] for row in rows]
                if len(ids) != len(set(ids)):
                    failures.append({"code": "duplicate_operation_ids"})
                for pair, expected in accepted.items():
                    if not _same_scalars(actual.get(pair), expected):
                        failures.append({"code": "incorrect_ledger_row", "tenant_id": pair[0], "request_id": pair[1]})
            except (sqlite3.Error, TypeError, ValueError) as exc:
                failures.append({"code": "ledger_unreadable", "error_type": type(exc).__name__})
            return failures

        def check_outbox(step):
            try:
                rows = bounded_rows("SELECT event_id,operation_id,version,payload FROM outbox")
                by_event = {row["event_id"]: row for row in rows}
                by_operation = {row["operation_id"]: row for row in rows}
                if len(rows) != len(by_event) or len(rows) != len(by_operation):
                    error("duplicate_outbox_rows", step)
                for event_id, previous in outbox_seen.items():
                    if by_event.get(event_id) != previous:
                        error("outbox_history_changed", step)
                expected_ids = {row["operation_id"] for row in accepted.values()}
                if set(by_operation) != expected_ids or None in expected_ids:
                    error("incorrect_outbox_identities", step)
                for row in rows:
                    if type(row["event_id"]) is not str or not row["event_id"] or type(row["operation_id"]) is not str or type(row["version"]) is not int or type(row["payload"]) is not str:
                        error("invalid_outbox_envelope", step)
                    else:
                        try:
                            json.loads(row["payload"])
                        except (TypeError, ValueError):
                            error("invalid_outbox_json", step)
                    outbox_seen.setdefault(row["event_id"], row)
            except (sqlite3.Error, TypeError, ValueError) as exc:
                error("outbox_unreadable", step, error_type=type(exc).__name__)

        def expected_request(request, phase):
            tenant, account = request["tenant_id"], request["account_id"]
            if request["op"] == "balance":
                return {"ok": True, "tenant_id": tenant, "account_id": account, "balance": balances[(tenant, account)]}, None
            pair = (tenant, request["request_id"])
            lookup_pair = global_keys.get(request["request_id"]) if phase == "overlap" else pair
            old = accepted.get(lookup_pair)
            if old is not None:
                if old["tenant_id"] != tenant or old["account_id"] != account or old["delta"] != request["delta"]:
                    return {"ok": False, "error": "idempotency_conflict"}, None
                return {"ok": True, "operation_id": old["operation_id"]}, None
            operation = json.dumps(["legacy", request["request_id"]], ensure_ascii=False, separators=(",", ":")) if phase == "overlap" else None
            accepted[pair] = {"tenant_id": tenant, "request_id": request["request_id"], "account_id": account, "delta": request["delta"], "operation_id": operation}
            balances[(tenant, account)] += request["delta"]
            if phase == "overlap":
                global_keys[request["request_id"]] = pair
            return {"ok": True, "operation_id": operation}, pair if operation is None else None

        def bind_new_id(pair, result, step):
            operation = result.get("operation_id") if isinstance(result, dict) else None
            if type(operation) is not str or not operation or any(row["operation_id"] == operation for other, row in accepted.items() if other != pair):
                error("invalid_new_operation_id", step)
                return
            expected = dict(accepted[pair], operation_id=operation)
            rows = [row for row in ledger_rows() if (row["tenant_id"], row["request_id"]) == pair]
            events = conn.execute("SELECT operation_id FROM outbox WHERE operation_id=?", (operation,)).fetchall()
            if result.get("ok") is not True or len(rows) != 1 or not _same_scalars(rows[0], expected) or len(events) != 1:
                error("operation_id_not_durably_bound", step)
                return
            accepted[pair]["operation_id"] = operation

        def deliver(pair, version, step):
            nonlocal deliveries
            expected = accepted.get(pair)
            if expected is None or expected["operation_id"] is None:
                error("delivery_missing_operation", step)
                return
            rows = conn.execute("SELECT * FROM outbox WHERE operation_id=?", (expected["operation_id"],)).fetchall()
            if len(rows) != 1:
                error("delivery_missing_or_duplicate_event", step)
                return
            event = dict(rows[0])
            event["payload"] = json.loads(event["payload"])
            result = legacy.consume(conn, copy.deepcopy(event)) if version == 1 else candidate("consumer", "consume", event)
            deliveries += 1
            types = {"tenant_id": str, "request_id": str, "account_id": str, "delta": int, "operation_id": str, "idempotency_key": str}
            if not isinstance(result, dict) or any(type(result.get(key)) is not kind for key, kind in types.items()) or not result["idempotency_key"]:
                error("malformed_settlement", step)
                return
            desired = dict(expected, idempotency_key=expected["operation_id"])
            if not _same_scalars(result, desired):
                error("incorrect_settlement_attempt", step, tenant_id=pair[0], request_id=pair[1])
            effect = {key: result[key] for key in ("tenant_id", "request_id", "account_id", "delta", "operation_id")}
            key = result["idempotency_key"]
            if key in sink:
                if sink[key] != effect:
                    error("sink_key_conflict", step)
            else:
                sink[key] = effect

        def backfill(limit):
            nonlocal cursor
            result = candidate("db", "backfill", cursor, limit)
            if not isinstance(result, dict) or type(result.get("done")) is not bool or (result.get("cursor") is not None and type(result["cursor"]) is not str) or (not result["done"] and result.get("cursor") == cursor):
                raise ValueError("invalid backfill progress")
            cursor = result.get("cursor")
            return result["done"]

        try:
            for index, step in enumerate(scenario["steps"]):
                try:
                    kind = step["kind"]
                    if kind == "expand":
                        candidate("db", "expand")
                        expanded = True
                    elif kind == "backfill":
                        backfill(step["limit"])
                    elif kind == "backfill_all":
                        cursor = None
                        for attempt in range(64):
                            if backfill(step["limit"]):
                                break
                        else:
                            raise ValueError("backfill did not finish")
                    elif kind == "request":
                        expected, new_pair = expected_request(step["request"], step["phase"])
                        if step["actor"] == 1:
                            with conn:
                                result = legacy.handle(conn, copy.deepcopy(step["request"]))
                        else:
                            result = candidate("api", "handle", step["request"], step["phase"])
                        if new_pair is not None:
                            bind_new_id(new_pair, result, index)
                            expected["operation_id"] = accepted[new_pair]["operation_id"]
                        if not _same_scalars(result, expected):
                            error("incorrect_request_result", index, operation=step["request"]["op"])
                    elif kind == "deliver":
                        for repeat in range(step.get("repeats", 1)):
                            deliver((step["tenant_id"], step["request_id"]), step["consumer"], index)
                    elif kind == "drain":
                        for pair in sorted(accepted):
                            deliver(pair, 2, index)
                    elif kind == "contract":
                        candidate("db", "contract")
                        contracted = True
                    else:
                        raise ValueError("unknown trace action")
                    completed += 1
                except Exception as exc:
                    if getattr(exc, "infrastructure_error", False):
                        raise
                    conn.rollback()
                    error("callback_error", index, action=step["kind"], error_type=type(exc).__name__)
                check_outbox(index)
                for failure in current_state_errors():
                    error(failure.pop("code"), index, **failure)
            static_errors = current_state_errors()
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='requests' AND type='table'").fetchone() is not None:
                static_errors.append({"code": "legacy_table_not_retired"})
            view = conn.execute("SELECT type FROM sqlite_master WHERE name='accepted_requests'").fetchone()
            if view is None or view[0] != "view":
                static_errors.append({"code": "missing_audit_view"})
            for pair, expected in accepted.items():
                effects = [effect for effect in sink.values() if (effect["tenant_id"], effect["request_id"]) == pair]
                if len(effects) != 1 or not _same_scalars(effects[0], expected):
                    error("incorrect_physical_effects", "final", tenant_id=pair[0], request_id=pair[1], count=len(effects))
            if any((effect["tenant_id"], effect["request_id"]) not in accepted for effect in sink.values()):
                error("unaccepted_physical_effect", "final")
        finally:
            conn.close()
    completion = {"passed": expanded and contracted and completed == len(scenario["steps"]), "expanded": expanded, "contracted": contracted, "completed_steps": completed, "total_steps": len(scenario["steps"]), "candidate_callbacks": callbacks, "deliveries": deliveries}
    invalid = any(item["code"] == "callback_error" for item in trace_errors)
    passed = not static_errors and not trace_errors and completion["passed"]
    return {"name": scenario["name"], "status": "candidate_invalid" if invalid else "scored", "score": None if invalid else float(passed), "passed": passed, "static": {"passed": not static_errors, "violations": static_errors}, "trace": {"passed": not trace_errors, "violations": trace_errors, "accepted_operations": len(accepted), "physical_effects": len(sink)}, "completion": completion}


def run_suite(candidate_dir, suite_name, invoke=None, invoke_factory=None):
    results = []
    for scenario in scenarios.suite(suite_name):
        if invoke_factory is None:
            results.append(execute(candidate_dir, scenario, invoke=invoke))
        else:
            with invoke_factory(candidate_dir) as dispatcher:
                results.append(execute(candidate_dir, scenario, invoke=dispatcher))
    invalid = any(result["status"] == "candidate_invalid" for result in results)
    passed = sum(result["passed"] for result in results)
    return {"suite": suite_name, "status": "candidate_invalid" if invalid else "scored", "cases": results, "passed": passed, "total": len(results), "score": None if invalid else passed / len(results)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--suite", choices=("public", "heldout", "all"), default="public")
    args = parser.parse_args()
    print(json.dumps(run_suite(args.candidate, args.suite), sort_keys=True))

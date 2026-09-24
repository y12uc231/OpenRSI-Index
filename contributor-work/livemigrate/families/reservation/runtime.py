"""Separate-store reservation migration draft.

Checks concrete deterministic causal schedules plus exact bounded client-history
linearizability. It does not exhaustively explore the distributed protocol state
space. Default callback loading is for trusted references/tests only.
"""
import argparse
import copy
import importlib.util
import json
import pathlib
import sqlite3
import sys
import tempfile
import uuid

import scenarios
from history import check_history

HERE = pathlib.Path(__file__).resolve().parent
NODES = {"source": "db", "gateway": "api", "A": "consumer", "B": "consumer"}
MAX_CALLBACKS = 6000
MAX_QUEUED = 2000
MAX_AUDIT_VM_STEPS = 2_000_000
MAX_AUDIT_BYTES = 2_097_152
SOURCE_SCHEMA = """
CREATE TABLE legacy_stock(sku TEXT PRIMARY KEY,total INTEGER NOT NULL,available INTEGER NOT NULL,epoch INTEGER NOT NULL,active INTEGER NOT NULL);
CREATE TABLE legacy_holds(reservation_id TEXT NOT NULL,sku TEXT NOT NULL,qty INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(reservation_id,sku));
CREATE TABLE legacy_requests(reservation_id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,status TEXT NOT NULL,lines_json TEXT NOT NULL);
"""


class CandidateInvalid(RuntimeError):
    pass


class AuditBudgetExceeded(RuntimeError):
    pass


class OracleRuntimeUnavailable(RuntimeError):
    infrastructure_error = True


def audit_rows(conn, sql):
    """Bound candidate-defined view evaluation as well as returned row count."""
    work = 0
    def progress():
        nonlocal work
        work += 1000
        return int(work >= MAX_AUDIT_VM_STEPS)
    conn.set_progress_handler(progress, 1000)
    try:
        rows, size = [], 0
        for row in conn.execute(sql):
            item = dict(row)
            size += len(json.dumps(item, sort_keys=True).encode("utf-8"))
            if size > MAX_AUDIT_BYTES:
                raise AuditBudgetExceeded("audit result byte bound exceeded")
            rows.append(item)
        return rows
    except sqlite3.Error as exc:
        if work >= MAX_AUDIT_VM_STEPS or "too big" in str(exc).lower():
            raise AuditBudgetExceeded("audit SQL work/value bound exceeded") from None
        raise
    finally:
        conn.set_progress_handler(None, 0)


def _module(path):
    spec = importlib.util.spec_from_file_location("reservation_" + uuid.uuid4().hex, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def trusted_invoker(candidate_dir):
    def invoke(role, function, conn, *args):
        # Each call mirrors a fresh isolated process. Only the public helper is
        # imported, never a peer reference implementation or oracle state.
        previous = sys.modules.get("legacy")
        sys.modules["legacy"] = _module(HERE / "reference" / "immutable_v1.py")
        try:
            module = _module(pathlib.Path(candidate_dir) / (role + ".py"))
            with conn:
                return getattr(module, function)(conn, *copy.deepcopy(args))
        finally:
            if previous is None:
                sys.modules.pop("legacy", None)
            else:
                sys.modules["legacy"] = previous
    return invoke


def execute(candidate_dir, scenario, invoke=None):
    scenario = copy.deepcopy(scenario)
    dispatcher = invoke if invoke is not None else trusted_invoker(candidate_dir)
    errors, invalid, audit_bound = [], False, False
    error_count = 0
    callbacks = logical_step = rounds_run = 0
    queue, queued = [], set()
    initialized = set()
    calls = {}
    effects = {}
    committed_ever = {}
    epoch_seen = {}
    fenced_epochs = {}
    snapshots = {}
    decisions = {}
    lost_reply = lost_output = False
    lost_output_trigger = None
    replayed = set()
    capacities = scenario["capacities"]

    def error(code, **details):
        nonlocal error_count
        error_count += 1
        if len(errors) < 100:
            errors.append(dict(code=code, step=logical_step, **details))

    def enqueue(src, to, body):
        if to not in NODES or not isinstance(body, dict):
            raise CandidateInvalid("invalid outbound destination/body")
        encoded = json.dumps([src, to, body], sort_keys=True, allow_nan=False)
        if encoded not in queued:
            if len(queue) >= MAX_QUEUED:
                raise CandidateInvalid("public queue work bound exceeded")
            queue.append((src, to, copy.deepcopy(body), encoded))
            queued.add(encoded)

    with tempfile.TemporaryDirectory(prefix="reservation-migrate-") as directory:
        conns = {}
        for node in NODES:
            folder = pathlib.Path(directory) / node
            folder.mkdir()
            conns[node] = sqlite3.connect(str(folder / "state.sqlite"))
            conns[node].row_factory = sqlite3.Row
            if hasattr(conns[node], "setlimit"):
                conns[node].setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_048_576)
            elif invoke is not None:
                raise OracleRuntimeUnavailable("isolated candidate auditing requires Python >=3.11 SQLite setlimit")
        conns["source"].executescript(SOURCE_SCHEMA)
        conns["source"].executemany("INSERT INTO legacy_stock VALUES(?,?,?,0,1)", [(sku, qty, qty) for sku, qty in capacities.items()])
        conns["source"].commit()

        def audit():
            nonlocal snapshots
            current = {}
            for node in ("source", "A", "B"):
                if node not in initialized:
                    continue
                conn = conns[node]
                try:
                    stocks = audit_rows(conn, "SELECT * FROM audit_inventory LIMIT 101")
                    holds = audit_rows(conn, "SELECT * FROM audit_holds LIMIT 501")
                    if len(stocks) > 100 or len(holds) > 500:
                        raise AuditBudgetExceeded("audit projection row bound exceeded")
                    stock_ids = [row["sku"] for row in stocks]
                    hold_ids = [(row["reservation_id"], row["sku"]) for row in holds]
                    if len(stock_ids) != len(set(stock_ids)) or len(hold_ids) != len(set(hold_ids)):
                        error("duplicate_audit_rows", node=node)
                    for stock in stocks:
                        sku = stock["sku"]
                        if sku not in capacities or any(type(stock.get(k)) is not int for k in ("total", "available", "epoch")) or stock["authority"] not in ("active", "staged", "fenced"):
                            error("malformed_inventory", node=node)
                            continue
                        local_holds = [h for h in holds if h["sku"] == sku]
                        malformed = any(type(h.get("qty")) is not int or h["qty"] <= 0 or h["state"] not in ("prepared", "committed", "released") or type(h["reservation_id"]) is not str for h in local_holds)
                        if malformed:
                            error("malformed_hold", node=node, sku=sku)
                            continue
                        used = sum(h["qty"] for h in local_holds if h["state"] != "released")
                        if stock["total"] != capacities[sku] or stock["available"] < 0 or used + stock["available"] != capacities[sku]:
                            error("capacity_conservation", node=node, sku=sku)
                        previous_epoch = epoch_seen.get((node, sku), -1)
                        if stock["epoch"] < previous_epoch:
                            error("epoch_regressed", node=node, sku=sku)
                        epoch_seen[(node, sku)] = max(previous_epoch, stock["epoch"])
                        if stock["authority"] == "fenced":
                            fenced_epochs[(node, sku)] = max(fenced_epochs.get((node, sku), -1), stock["epoch"])
                        elif stock["authority"] == "active" and stock["epoch"] <= fenced_epochs.get((node, sku), -1):
                            error("fenced_epoch_reactivated", node=node, sku=sku)
                        for hold in local_holds:
                            if not any(call["reservation_id"] == hold["reservation_id"] and call["lines"].get(sku) == hold["qty"] for call in calls.values()):
                                error("unrequested_hold", node=node, sku=sku)
                        current[(node, sku)] = (stock, local_holds)
                    if node == "source":
                        actual = {row["sku"]: row for row in audit_rows(conn, "SELECT * FROM legacy_stock LIMIT 101")}
                        if set(actual) != set(stock_ids):
                            error("source_audit_mismatch")
                        for stock in stocks:
                            base = actual.get(stock["sku"], {})
                            if any(stock[field] != base.get(field) for field in ("total", "available", "epoch")) or (stock["authority"] == "active") != bool(base.get("active")):
                                error("source_audit_mismatch", sku=stock["sku"])
                        actual_holds = audit_rows(conn, "SELECT reservation_id,sku,qty,state FROM legacy_holds LIMIT 501")
                        if sorted(json.dumps(row, sort_keys=True) for row in holds) != sorted(json.dumps(row, sort_keys=True) for row in actual_holds):
                            error("source_hold_audit_mismatch")
                except (sqlite3.Error, KeyError, TypeError, ValueError) as exc:
                    error("audit_unreadable", node=node, error_type=type(exc).__name__)
            for sku in capacities:
                active = [(node, stock, holds) for (node, row_sku), (stock, holds) in current.items() if row_sku == sku and stock["authority"] == "active"]
                if len(active) > 1:
                    error("multiple_active_owners", sku=sku)
                for node, stock, holds in active:
                    if node != "source":
                        old = current.get(("source", sku))
                        if old is None or old[0]["authority"] != "fenced" or stock["epoch"] <= old[0]["epoch"]:
                            error("activation_without_source_fence", sku=sku, node=node)
                    for hold in holds:
                        if hold["state"] == "committed":
                            key = (hold["reservation_id"], sku)
                            if key in committed_ever and committed_ever[key] != hold["qty"]:
                                error("committed_quantity_changed", sku=sku)
                            committed_ever[key] = hold["qty"]
                    local = {h["reservation_id"]: h for h in holds if h["state"] == "committed"}
                    for (rid, previous_sku), qty in committed_ever.items():
                        if previous_sku == sku and (rid not in local or local[rid]["qty"] != qty):
                            error("committed_hold_lost", node=node, sku=sku, reservation_id=rid)
            snapshots = current

            if "gateway" in initialized:
                rows = audit_rows(conns["gateway"], "SELECT * FROM audit_decisions LIMIT 101")
                current_decisions = {}
                if len(rows) > 100:
                    raise AuditBudgetExceeded("decision audit row bound exceeded")
                for row in rows:
                    try:
                        rid, state = row["reservation_id"], row["state"]
                        lines = json.loads(row["lines_json"])
                        valid = type(rid) is str and state in ("commit", "abort") and type(lines) is dict and all(type(qty) is int and qty > 0 and sku in capacities for sku, qty in lines.items()) and bool(lines)
                        valid = valid and any(call["reservation_id"] == rid and call["lines"] == lines for call in calls.values())
                        if not valid or rid in current_decisions:
                            error("invalid_global_decision")
                            continue
                        current_decisions[rid] = (state, lines)
                        if rid in decisions and decisions[rid] != (state, lines):
                            error("global_decision_changed", reservation_id=rid)
                        decisions.setdefault(rid, (state, lines))
                    except (KeyError, TypeError, ValueError):
                        error("invalid_global_decision")
                for rid, (state, lines) in decisions.items():
                    if rid not in current_decisions:
                        error("global_decision_lost", reservation_id=rid)
                    if state == "commit" and not reserved_lines(rid, lines):
                        error("global_commit_without_reserved_lines", reservation_id=rid)
            for rid, lines in effects.items():
                if not reserved_lines(rid, lines):
                    error("fulfilled_reservation_lost", reservation_id=rid)

        def reserved_lines(rid, lines, require_committed=False):
            for sku, qty in lines.items():
                owners = [(s, h) for (node, row_sku), (s, h) in snapshots.items() if row_sku == sku]
                active = [(s, h) for s, h in owners if s["authority"] == "active"]
                # During a handoff gap the fenced/staged durable copies retain
                # the obligation. Once an owner is active, its copy must do so.
                relevant = active if active else owners
                states = ("committed",) if require_committed else ("prepared", "committed")
                if len(active) > 1 or not any(any(h["reservation_id"] == rid and h["state"] in states and h["qty"] == qty for h in holds) for stock, holds in relevant):
                    return False
            return True

        def committed_lines(rid, lines):
            return reserved_lines(rid, lines, require_committed=True) or (decisions.get(rid) == ("commit", lines) and reserved_lines(rid, lines))

        def accept_reply(node, reply):
            nonlocal lost_reply
            required = {"call_id", "reservation_id", "status", "lines"}
            if node not in ("source", "gateway") or not isinstance(reply, dict) or not required.issubset(reply):
                raise CandidateInvalid("invalid client reply envelope")
            if type(reply["call_id"]) is not str or type(reply["reservation_id"]) is not str or type(reply["lines"]) is not dict or any(type(k) is not str or type(v) is not int for k, v in reply["lines"].items()):
                error("incorrect_client_reply", node=node)
                return
            call = calls.get(reply["call_id"])
            if call is None or reply["reservation_id"] != call["reservation_id"] or reply["lines"] != call["lines"] or reply["status"] not in ("committed", "out_of_stock", "idempotency_conflict"):
                error("incorrect_client_reply", node=node)
                return
            if reply["status"] == "committed":
                rid = call["reservation_id"]
                if not committed_lines(rid, call["lines"]):
                    error("fulfillment_without_commit_certificate", reservation_id=rid)
                previous = effects.get(rid)
                if previous is not None and previous != call["lines"]:
                    error("fulfillment_identity_conflict", reservation_id=rid)
                elif previous is None:
                    effects[rid] = copy.deepcopy(call["lines"])
                # Effect commits, but caller and server receive no ACK once.
                if scenario.get("lose_reply_once") and not lost_reply and node == "gateway":
                    lost_reply = True
                    return
            if call["response_step"] is None:
                call["response_step"] = logical_step
                call["status"] = reply["status"]
            elif call["status"] != reply["status"]:
                error("client_receipt_changed", call_id=reply["call_id"])
            enqueue("driver", node, {"kind": "reply_ack", "call_id": reply["call_id"]})
            if call["node"] != node:
                enqueue("driver", call["node"], {"kind": "reply_ack", "call_id": reply["call_id"]})

        def deliver(src, node, body):
            nonlocal callbacks, logical_step, invalid, lost_output, lost_output_trigger, audit_bound
            if invalid or audit_bound:
                return
            if callbacks >= MAX_CALLBACKS:
                invalid = True
                error("candidate_invalid", node=node, error_type="CallbackWorkBound")
                return
            callbacks += 1
            logical_step += 1
            conn = conns[node]
            conn.commit()
            try:
                output = dispatcher(NODES[node], "on_message", conn, {"src": src, "body": copy.deepcopy(body)})
                conn.row_factory = sqlite3.Row
                if src == "driver" and body.get("kind") == "init":
                    initialized.add(node)
                if not isinstance(output, dict) or set(output) != {"messages", "replies"} or not isinstance(output["messages"], list) or not isinstance(output["replies"], list):
                    raise CandidateInvalid("invalid callback output")
                audit()
                fault_sku = scenario.get("lose_output_after_fence")
                fence = snapshots.get(("source", fault_sku), ({}, []))[0]
                if scenario.get("lose_output_once") == node and not lost_output and output["messages"] and fence.get("authority") == "fenced":
                    lost_output = True
                    input_kind = body.get("kind") if type(body.get("kind")) is str else "private_message"
                    lost_output_trigger = {"step": logical_step, "node": node, "input_kind": input_kind, "sku": fault_sku}
                    return
                for packet in output["messages"]:
                    if not isinstance(packet, dict) or set(packet) != {"to", "body"}:
                        raise CandidateInvalid("invalid outbound packet")
                    enqueue(node, packet["to"], packet["body"])
                for reply in output["replies"]:
                    accept_reply(node, reply)
            except AuditBudgetExceeded:
                audit_bound = True
                error("audit_budget_exhausted", node=node)
            except Exception as exc:
                if getattr(exc, "infrastructure_error", False):
                    raise
                conn.rollback()
                invalid = True
                error("candidate_invalid", node=node, error_type=type(exc).__name__)

        try:
            for node in NODES:
                deliver("driver", node, {"kind": "init", "node_id": node, "capacities": capacities, "routing": {sku: "source" for sku in capacities}})
            for step in scenario["steps"]:
                logical_step += 1
                if step["kind"] == "client":
                    if step["call_id"] in calls:
                        raise ValueError("scenario repeats a call id")
                    calls[step["call_id"]] = {key: copy.deepcopy(step[key]) for key in ("call_id", "reservation_id", "lines", "node")}
                    calls[step["call_id"]].update(invoke_step=logical_step, response_step=None, status=None)
                    enqueue("driver", step["node"], {key: copy.deepcopy(step[key]) for key in ("kind", "call_id", "reservation_id", "lines")})
                elif step["kind"] == "move":
                    enqueue("driver", "source", dict(step))
                elif step["kind"] == "require_reply":
                    if calls[step["call_id"]]["response_step"] is None:
                        error("stable_window_progress_failure", call_id=step["call_id"])
                elif step["kind"] == "run":
                    blocked = {tuple(link) for link in step["blocked"]}
                    paused = set(step["paused"])
                    priorities = {node: index for index, node in enumerate(scenario["delivery_order"])}
                    for unused in range(step["rounds"]):
                        rounds_run += 1
                        if invalid or audit_bound:
                            break
                        pending = sorted(queue, key=lambda item: priorities[item[1]])
                        queue.clear()
                        queued.clear()
                        for src, node, body, encoded in pending:
                            if node in paused or (src, node) in blocked:
                                enqueue(src, node, body)
                                continue
                            deliver(src, node, body)
                            if scenario.get("replay") and src in NODES and encoded not in replayed:
                                replayed.add(encoded)
                                deliver(src, node, body)
                        for node in scenario["delivery_order"]:
                            if node not in paused:
                                deliver("driver", node, {"kind": "tick"})
                else:
                    raise ValueError("unknown scenario instruction")
                if invalid or audit_bound:
                    break
            if not audit_bound and not invalid:
                try:
                    audit()
                except AuditBudgetExceeded:
                    audit_bound = True
                    error("audit_budget_exhausted", node="final_audit")
                except Exception as exc:
                    if getattr(exc, "infrastructure_error", False):
                        raise
                    invalid = True
                    error("candidate_invalid", node="final_audit", error_type=type(exc).__name__)
            target_ok = all((owner, sku) in snapshots and snapshots[(owner, sku)][0]["authority"] == "active" and snapshots.get(("source", sku), ({}, []))[0].get("authority") == "fenced" for sku, owner in (("X", "A"), ("Y", "B")))
            history_result = check_history(capacities, list(calls.values()))
            for rid, lines in effects.items():
                if not any(call["reservation_id"] == rid and call["lines"] == lines for call in calls.values()):
                    error("unrequested_fulfillment", reservation_id=rid)
                if not reserved_lines(rid, lines, require_committed=True):
                    error("committed_participants_incomplete", reservation_id=rid)
            for call in calls.values():
                if call["status"] == "committed" and effects.get(call["reservation_id"]) != call["lines"]:
                    error("missing_fulfillment", call_id=call["call_id"])
            static_errors = []
            for sku in capacities:
                consumed = sum(lines.get(sku, 0) for lines in effects.values())
                active = [stock for (node, row_sku), (stock, holds) in snapshots.items() if row_sku == sku and stock["authority"] == "active"]
                if len(active) != 1 or active[0]["available"] != capacities[sku] - consumed:
                    static_errors.append({"code": "incorrect_final_capacity", "sku": sku})
            if not target_ok:
                static_errors.append({"code": "handoff_incomplete"})
            completion = {"passed": target_ok and all(c["response_step"] is not None for c in calls.values()), "resolved_calls": sum(c["response_step"] is not None for c in calls.values()), "total_calls": len(calls), "candidate_callbacks": callbacks, "fair_rounds": rounds_run, "queued_messages": len(queue)}
            bound_exhausted = history_result["reason"] == "bound_exhausted"
            status = "candidate_invalid" if invalid else "unscored_audit_bound" if audit_bound else "unscored_checker_bound" if bound_exhausted else "scored"
            passed = not error_count and not static_errors and completion["passed"] and history_result["passed"] and status == "scored"
            return {"name": scenario["name"], "status": status, "passed": passed, "score": float(passed) if status == "scored" else None,
                    "static": {"passed": not static_errors, "violations": static_errors},
                    "trace": {"passed": error_count == 0, "violation_count": error_count, "violations": errors, "physical_fulfillments": len(effects)},
                    "history": history_result, "completion": completion,
                    "faults": {"lost_output": lost_output, "lost_output_trigger": lost_output_trigger, "lost_effect_ack": lost_reply, "replayed_packets": len(replayed)},
                    "coverage": "declared causal schedules; exhaustive checker only for each observed finite client history"}
        finally:
            for conn in conns.values():
                conn.close()


def run_suite(candidate_dir, suite_name, invoke=None, invoke_factory=None):
    results = []
    for scenario in scenarios.suite(suite_name):
        if invoke_factory:
            with invoke_factory(candidate_dir) as dispatch:
                results.append(execute(candidate_dir, scenario, dispatch))
        else:
            results.append(execute(candidate_dir, scenario, invoke))
    scored = all(r["status"] == "scored" for r in results)
    passed = sum(r["passed"] for r in results)
    return {"suite": suite_name, "status": "scored" if scored else "unscored", "cases": results, "passed": passed, "total": len(results), "score": passed / len(results) if scored else None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--suite", choices=("public", "heldout", "all"), default="public")
    args = parser.parse_args()
    print(json.dumps(run_suite(args.candidate, args.suite), sort_keys=True))

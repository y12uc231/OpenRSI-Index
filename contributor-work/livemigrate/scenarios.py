"""Deterministic traffic, not embedded oracle answers or candidate labels.

All variants exercise one migration family. The public trace is disclosed;
held-out trace data belongs only to the trusted evaluator in a scored run.
"""
import copy


def _request(actor, op, order, **values):
    return {"kind": "request", "actor": actor, "phase": values.pop("phase", "overlap"), "request": dict(op=op, order_id=order, **values)}


def _delivery(payment, consumer, repeats=1):
    return {"kind": "deliver", "payment_id": payment, "consumer": consumer, "repeats": repeats}


def make_scenario(name, scale=1, reverse_delivery=False, rollback=True):
    # Input values only; the runtime derives the reference ledger from requests.
    steps = [
        _request(1, "pay", "A", expected_revision=1, payment_id="p_preexisting"),
        {"kind": "expand"}, {"kind": "backfill", "limit": 1},
        _request(2, "get", "B"),
        _request(1, "put", "A", expected_revision=1, amount_cents=1500 * scale),
        _request(2, "pay", "A", expected_revision=2, payment_id="p_stale"),
        _request(2, "put", "B", expected_revision=1, amount_micros=70000000 * scale),
        _request(1, "get", "B"),
        _request(1, "pay", "B", expected_revision=2, payment_id="p_delayed"),
        _request(2, "put", "B", expected_revision=2, amount_micros=90000000 * scale),
        {"kind": "backfill", "limit": 1},
    ]
    deliveries = [_delivery("p_stale", 1), _delivery("p_stale", 2), _delivery("p_delayed", 2, 2)]
    steps.extend(reversed(deliveries) if reverse_delivery else deliveries)
    if rollback:
        steps += [
            _request(1, "put", "C", expected_revision=1, amount_cents=4100 * scale),
            _request(2, "pay", "C", expected_revision=2, payment_id="p_rollback"),
            _delivery("p_rollback", 1), _delivery("p_rollback", 2),
        ]
    steps += [
        _request(1, "put", "D", expected_revision=0, amount_cents=1700 * scale),
        _request(2, "get", "D"),
        _request(1, "pay", "D", expected_revision=1, payment_id="p_late"),
        _delivery("p_late", 2, 2),
        _request(2, "pay", "A", expected_revision=999, payment_id="p_conflict"),
        _request(2, "pay", "B", expected_revision=3, payment_id="p_stale"),
        {"kind": "backfill_all", "limit": 2},
        {"kind": "drain"}, {"kind": "contract"},
        _request(2, "put", "A", expected_revision=2, amount_micros=1234567 * scale, phase="v2_only"),
        _request(2, "pay", "A", expected_revision=3, payment_id="p_micros", phase="v2_only"),
        _request(2, "put", "A", expected_revision=3, amount_micros=7777777 * scale, phase="v2_only"),
        _request(2, "pay", "A", expected_revision=3, payment_id="p_micros", phase="v2_only"),
        _delivery("p_micros", 2, 2),
        _request(2, "get", "A", phase="v2_only"), {"kind": "drain"},
        _delivery("p_preexisting", 2, 2),
    ]
    return {"name": name, "initial_orders": [{"order_id": key, "revision": 1, "amount_cents": amount * scale} for key, amount in [("A", 1000), ("B", 2000), ("C", 3000)]], "steps": steps}


PUBLIC = [make_scenario("public_overlap", rollback=False)]
HELDOUT = [
    make_scenario("late_write_and_rollback", scale=3),
    make_scenario("reordered_delivery", scale=7, reverse_delivery=True),
    make_scenario("delayed_legacy_event", scale=11, reverse_delivery=True, rollback=False),
]


def suite(name):
    if name not in ("public", "heldout", "all"):
        raise ValueError("unknown suite")
    return copy.deepcopy(PUBLIC if name == "public" else HELDOUT if name == "heldout" else PUBLIC + HELDOUT)

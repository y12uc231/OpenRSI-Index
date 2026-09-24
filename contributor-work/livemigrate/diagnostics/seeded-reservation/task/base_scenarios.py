"""Declared causal schedules, not exhaustive protocol-state exploration."""
import copy


def client(call_id, reservation_id, lines, node="gateway"):
    return {"kind": "client", "node": node, "call_id": call_id, "reservation_id": reservation_id, "lines": lines}


def rounds(count, blocked=None, paused=None):
    return {"kind": "run", "rounds": count, "blocked": blocked or [], "paused": paused or []}


def make(name, order=None, replay=False, lose_reply=False, lose_output=None):
    return {"name": name, "capacities": {"X": 3, "Y": 3, "Z": 2},
            "delivery_order": order or ["source", "A", "B", "gateway"], "replay": replay,
            "lose_reply_once": lose_reply, "lose_output_once": lose_output, "lose_output_after_fence": "X" if lose_output else None,
            "steps": [
                client("old-call", "old", {"X": 1, "Y": 1}, "source"), rounds(8),
                {"kind": "move", "sku": "X", "destination": "A"}, rounds(10),
                client("bundle-call", "bundle", {"X": 1, "Y": 1}),
                rounds(3, blocked=[["A", "gateway"]]),
                {"kind": "move", "sku": "Y", "destination": "B"},
                client("z-call", "independent", {"Z": 1}),
                rounds(10, blocked=[["A", "gateway"]]),
                {"kind": "require_reply", "call_id": "z-call"},
                rounds(28),
                client("partial-abort-call", "partial-abort", {"X": 2, "Y": 1}),
                client("changed-retry", "old", {"Z": 1}), rounds(18),
                client("old-retry", "old", {"X": 1, "Y": 1}),
                client("new-call", "after-retirement", {"X": 1, "Y": 1}),
                rounds(20, paused=["source"]),
                {"kind": "require_reply", "call_id": "new-call"},
                client("overflow-call", "overflow", {"X": 1}), rounds(16),
            ]}


PUBLIC = [make("public_prepared_hold_handoff")]
HELDOUT = [make("replayed_handoff_and_decisions", replay=True, order=["gateway", "B", "A", "source"]),
           make("lost_committed_reply", lose_reply=True, order=["A", "gateway", "source", "B"]),
           make("lost_source_send_after_fence", lose_output="source", replay=True, order=["B", "gateway", "source", "A"])]


def suite(name):
    if name not in ("public", "heldout", "all"):
        raise ValueError("unknown suite")
    return copy.deepcopy(PUBLIC if name == "public" else HELDOUT if name == "heldout" else PUBLIC + HELDOUT)

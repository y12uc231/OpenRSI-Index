"""Exact linearizability decision for a bounded, completed client history.

This explores admissible sequentializations of ONE observed history, not all
message schedules of a distributed protocol. It accepts either legitimate
winner among concurrent reservations. No candidate state or reference service
implementation supplies the expected answer.
"""
from functools import lru_cache

MAX_CALLS = 12
STATE_LIMIT = 100000
STATUSES = {'committed', 'out_of_stock', 'idempotency_conflict'}


class _BoundExhausted(Exception):
    pass


def check_history(capacities, calls):
    """Return passed/reason/explored/exhaustive without mutating either input.

    ``exhaustive`` means all status-consistent reachable sequential-prefix states
    were examined (equivalent states are memoized). Even a passing search explores
    all such states rather than stopping at its first witness. A budget limit is
    an incomplete decision, never evidence of non-linearizability. ``explored``
    counts distinct prefix states, including the initial/terminal states.
    """
    def result(passed, reason, explored=0, exhaustive=False):
        return dict(passed=passed, reason=reason, explored=explored, exhaustive=exhaustive)

    if not isinstance(capacities, dict) or not isinstance(calls, list):
        return result(False, 'invalid_history')
    if any(type(sku) is not str or not sku or type(qty) is not int or qty < 0
           for sku, qty in capacities.items()):
        return result(False, 'invalid_history')
    if len(calls) > MAX_CALLS:
        return result(False, 'bound_exhausted')
    skus = tuple(sorted(capacities))
    sku_index = {sku: i for i, sku in enumerate(skus)}
    seen_calls, parsed = set(), []
    pending = False
    for call in calls:
        if not isinstance(call, dict):
            return result(False, 'invalid_history')
        call_id, rid = call.get('call_id'), call.get('reservation_id')
        lines = call.get('lines')
        begin, end, status = call.get('invoke_step'), call.get('response_step'), call.get('status')
        if type(call_id) is not str or not call_id or call_id in seen_calls \
                or type(rid) is not str or not rid or type(begin) is not int or begin < 0 \
                or not isinstance(lines, dict) or not lines \
                or any(type(sku) is not str or sku not in capacities or type(qty) is not int or qty <= 0
                       for sku, qty in lines.items()):
            return result(False, 'invalid_history')
        seen_calls.add(call_id)
        if end is None:
            if status is not None:
                return result(False, 'invalid_history')
            pending = True
        elif type(end) is not int or end < begin or type(status) is not str or status not in STATUSES:
            return result(False, 'invalid_history')
        parsed.append((rid, tuple(sorted(lines.items())), begin, end, status))
    if pending:
        return result(False, 'incomplete_history')

    predecessors = []
    for _, _, begin, _, _ in parsed:
        predecessors.append(sum(1 << j for j, other in enumerate(parsed) if other[3] < begin))
    complete = (1 << len(parsed)) - 1
    explored = 0

    @lru_cache(maxsize=None)
    def visit(done, available, ledger):
        nonlocal explored
        if explored >= STATE_LIMIT:
            raise _BoundExhausted()
        explored += 1
        if done == complete:
            return True
        receipts = {rid: (payload, status) for rid, payload, status in ledger}
        found = False
        for index, (rid, payload, _, _, observed) in enumerate(parsed):
            bit = 1 << index
            if done & bit or predecessors[index] & ~done:
                continue
            next_available, next_ledger = available, ledger
            if rid in receipts:
                original, cached_status = receipts[rid]
                expected = cached_status if payload == original else 'idempotency_conflict'
            else:
                sufficient = all(available[sku_index[sku]] >= qty for sku, qty in payload)
                expected = 'committed' if sufficient else 'out_of_stock'
                if expected == observed:
                    next_ledger = tuple(sorted(ledger + ((rid, payload, expected),)))
                    if sufficient:
                        values = list(available)
                        for sku, qty in payload:
                            values[sku_index[sku]] -= qty
                        next_available = tuple(values)
            if expected != observed:
                continue
            # Do not short-circuit: exhaustive refers to this bounded history's
            # status-consistent prefix graph, not just the first valid witness.
            branch = visit(done | bit, next_available, next_ledger)
            found = branch or found
        return found

    try:
        passed = visit(0, tuple(capacities[sku] for sku in skus), ())
    except _BoundExhausted:
        return result(False, 'bound_exhausted', explored)
    return result(passed, 'linearizable' if passed else 'not_linearizable', explored, True)

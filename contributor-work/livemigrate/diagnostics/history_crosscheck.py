"""Independent full-permutation check of the bounded history oracle; no models."""
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import random


def brute_force(capacities, calls):
    for order in itertools.permutations(range(len(calls))):
        positions = {index: position for position, index in enumerate(order)}
        if any(a['response_step'] < b['invoke_step'] and positions[i] > positions[j]
               for i, a in enumerate(calls) for j, b in enumerate(calls)):
            continue
        stock, receipts = dict(capacities), {}
        matches = True
        for index in order:
            call = calls[index]
            rid, lines = call['reservation_id'], call['lines']
            if rid in receipts:
                original, outcome = receipts[rid]
                if original != lines:
                    outcome = 'idempotency_conflict'
            else:
                outcome = 'committed' if all(stock[k] >= q for k, q in lines.items()) else 'out_of_stock'
                receipts[rid] = (dict(lines), outcome)
                if outcome == 'committed':
                    for sku, qty in lines.items():
                        stock[sku] -= qty
            if outcome != call['status']:
                matches = False
                break
        if matches:
            return True
    return False


def main():
    source = Path(__file__).resolve().parents[1] / 'families/reservation/history.py'
    before = source.read_bytes()
    spec = importlib.util.spec_from_file_location('trusted_history_crosscheck', source)
    history = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(history)
    rng = random.Random(2031)
    positives = 0
    for trial in range(2000):
        capacities = {sku: rng.randrange(4) for sku in ('X', 'Y')}
        calls = []
        for i in range(rng.randrange(1, 6)):
            lines = {sku: rng.randrange(1, 4) for sku in ('X', 'Y') if rng.randrange(2)}
            if not lines:
                lines = {'X': 1}
            begin = rng.randrange(8)
            calls.append({'call_id': str(i), 'reservation_id': str(rng.randrange(3)),
                          'lines': lines, 'invoke_step': begin,
                          'response_step': begin + rng.randrange(1, 6),
                          'status': rng.choice(('committed', 'out_of_stock', 'idempotency_conflict'))})
        expected = brute_force(capacities, calls)
        actual = history.check_history(capacities, calls)
        if actual['passed'] != expected or not actual['exhaustive']:
            raise AssertionError({'trial': trial, 'capacities': capacities, 'calls': calls,
                                  'expected': expected, 'actual': actual})
        positives += expected
    if source.read_bytes() != before or not 0 < positives < 2000:
        raise AssertionError('source changed or the sample lacks both outcomes')
    print(json.dumps({'seed': 2031, 'histories': 2000, 'maximum_calls': 5,
                      'linearizable': positives, 'not_linearizable': 2000 - positives,
                      'disagreements': 0, 'history_source_sha256': hashlib.sha256(before).hexdigest(),
                      'scope': 'finite seeded cross-check, not a formal proof of the checker'}))


if __name__ == '__main__':
    main()

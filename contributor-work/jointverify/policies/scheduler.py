"""Pure scheduling callbacks. Never inspect task IDs, hidden tests, or oracles."""
from __future__ import annotations

from copy import deepcopy


class Policy:
    def __init__(self, config: dict):
        self.config = deepcopy(config)
        if config.get('mode') not in {'periodic', 'always_verify', 'adaptive'}:
            raise ValueError('Unknown policy mode.')
        interval = config.get('interval', 2)
        if isinstance(interval, bool) or not isinstance(interval, int) or interval < 1:
            raise ValueError('interval must be a positive integer.')

    def action(self, state: dict) -> dict:
        return action(state, self.config)


def _risk(workers):
    evidence = []
    for index, left in enumerate(workers):
        for right in workers[index + 1:]:
            paths = set(left.get('changed_paths', [])) & set(right.get('changed_paths', []))
            dependencies = ((set(left.get('exports', [])) & set(right.get('imports', []))) |
                            (set(right.get('exports', [])) & set(left.get('imports', []))))
            if paths:
                evidence.append('changed-path overlap')
            if dependencies:
                evidence.append('syntactic cross-worker symbol dependency')
    return sorted(set(evidence))


def action(state: dict, config: dict | None = None) -> dict:
    """Select a worker/public check/finish using runner-observed state only.

    `joint_verify` means integrate current patches and run PUBLIC tests. The
    independent final hidden-test Judge is outside this callback and always runs.
    Changed paths/exports/imports are heuristics, not correctness certificates.
    """
    config = config or {'mode': 'periodic', 'interval': 2}
    mode = config.get('mode')
    if mode not in {'periodic', 'always_verify', 'adaptive'}:
        raise ValueError('Unknown policy mode.')
    interval = config.get('interval', 2)
    if isinstance(interval, bool) or not isinstance(interval, int) or interval < 1:
        raise ValueError('interval must be a positive integer.')
    workers = state.get('workers', [])
    if not workers or len({w['id'] for w in workers}) != len(workers):
        raise ValueError('At least one worker with unique IDs is required.')
    for name in ['worker_calls_remaining', 'checks_remaining', 'turns_since_verify']:
        value = state.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f'{name} must be a nonnegative integer.')
    for worker in workers:
        turns = worker.get('turns', 0)
        if isinstance(turns, bool) or not isinstance(turns, int) or turns < 0:
            raise ValueError('Worker turns must be nonnegative integers.')

    dirty = state.get('candidate_hash') != state.get('verified_hash')
    has_candidate = state.get('candidate_hash') is not None
    remaining = state['worker_calls_remaining']
    checks = state['checks_remaining']
    failed = state.get('last_verify_passed') is False
    all_done = all(w.get('done', False) for w in workers)
    can_verify = has_candidate and dirty and checks > 0

    def decision(kind, reason, worker=None):
        context = []
        if worker is not None:
            for other in workers:
                message = other.get('message')
                if other['id'] != worker['id'] and message:
                    context.append(f"Message from {other['id']}: {message}")
            if state.get('verification_feedback'):
                context.append('Latest public verification feedback for candidate '
                               f"{state.get('verified_hash')}: {state['verification_feedback']}")
        return {'action': kind, 'worker_id': worker['id'] if worker else None,
                'integrate': kind == 'joint_verify', 'message_context': context,
                'reason': reason}

    # A final public check is useful if affordable, but hidden Judge grading is
    # never conditioned on this budget. Finishing dirty does not mean unscored.
    if remaining == 0 or (all_done and not failed):
        if can_verify:
            return decision('joint_verify', 'final public verification barrier')
        return decision('finish', 'worker work complete or call budget exhausted; final Judge still required')

    # Do not repeatedly re-test an unchanged failure. Give a worker a repair
    # opportunity first, then all controls recheck its changed candidate.
    if failed and can_verify:
        return decision('joint_verify', 'retest changed candidate after public failure feedback')
    if not failed and can_verify:
        if mode == 'always_verify':
            return decision('joint_verify', 'candidate hash changed since public verification')
        if mode == 'adaptive':
            risks = _risk(workers)
            if risks:
                return decision('joint_verify', 'dirty candidate with ' + '; '.join(risks))
        if state['turns_since_verify'] >= interval:
            return decision('joint_verify', 'scheduled periodic public verification')

    available = workers if failed else [w for w in workers if not w.get('done', False)]
    if not available:
        return decision('finish', 'no active worker; final Judge still required')
    # Common scheduling for every control: fewest turns, then rotate ties away
    # from the last worker, then preserve runner-supplied stable worker order.
    selected = min(available, key=lambda w: (w.get('turns', 0), w['id'] == state.get('last_worker_id')))
    return decision('worker', 'repair public failure' if failed else 'balanced worker turn', selected)

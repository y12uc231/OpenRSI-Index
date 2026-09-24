"""Declared draft workload traces. No model outcomes informed these inputs."""
import copy


def credit(actor, tenant, key, delta, phase="overlap", account="wallet"):
    return {"kind": "request", "actor": actor, "phase": phase, "request": {"op": "credit", "tenant_id": tenant, "request_id": key, "account_id": account, "delta": delta}}


def balance(tenant, account="wallet", actor=2, phase="overlap"):
    return {"kind": "request", "actor": actor, "phase": phase, "request": {"op": "balance", "tenant_id": tenant, "account_id": account}}


def deliver(tenant, key, consumer=2, repeats=1):
    return {"kind": "deliver", "tenant_id": tenant, "request_id": key, "consumer": consumer, "repeats": repeats}


def make(name, key="shared", reordered=False, odd_keys=False):
    steps = [
        credit(1, "alpha", key, 7), deliver("alpha", key, consumer=1),
        credit(1, "alpha", "z-last", 3),
        {"kind": "expand"}, {"kind": "backfill", "limit": 1},
        credit(2, "alpha", "middle", 5),
        credit(1, "alpha", "middle", 5),
        deliver("alpha", "middle", consumer=1),
        credit(1, "beta", "0-behind-cursor", 2),
        credit(2, "beta", key, 11),  # Must conflict until v1 retirement.
        balance("alpha", actor=1), balance("beta"),
        {"kind": "backfill", "limit": 1},
        credit(2, "alpha", key, 7, phase="retired"),
        credit(2, "beta", key, 11, phase="retired"),
        credit(2, "beta", key, 99, phase="retired"),
        credit(2, "beta", key, 11, phase="retired", account="reserve"),
    ]
    deliveries = [deliver("alpha", key, repeats=2), deliver("beta", key, repeats=2)]
    steps.extend(reversed(deliveries) if reordered else deliveries)
    if odd_keys:
        steps += [credit(2, "a:b", "c", 13, phase="retired"), credit(2, "a", "b:c", 17, phase="retired"),
                  credit(2, "alpha", '["legacy", "雪:quote\\"]', 19, phase="retired")]
    steps += [
        {"kind": "backfill_all", "limit": 2}, {"kind": "drain"}, {"kind": "contract"},
        credit(2, "alpha", key, 7, phase="complete"),
        credit(2, "beta", "z-last", 23, phase="complete"),
        credit(2, "alpha", "middle", 5, phase="complete"),
        deliver("alpha", key, repeats=2),
        balance("alpha", phase="complete"), balance("beta", phase="complete"),
        {"kind": "drain"},
    ]
    return {"name": name, "accounts": [{"tenant_id": tenant, "account_id": account, "balance": 0} for tenant in ("alpha", "beta", "a:b", "a") for account in ("wallet", "reserve")], "steps": steps}


PUBLIC = [make("public_identity_overlap")]
HELDOUT = [make("legacy_retry_after_scoped_collision", reordered=True),
           make("delimiter_and_unicode_identities", key="root:shared", odd_keys=True),
           make("replay_after_legacy_retirement", key='["tenant","beta","x"]', reordered=True, odd_keys=True)]


def suite(name):
    if name not in ("public", "heldout", "all"):
        raise ValueError("unknown suite")
    return copy.deepcopy(PUBLIC if name == "public" else HELDOUT if name == "heldout" else PUBLIC + HELDOUT)

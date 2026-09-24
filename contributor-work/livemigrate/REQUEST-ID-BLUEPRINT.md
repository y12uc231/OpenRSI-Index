# Request-ID migration: implementation blueprint, not a frozen task

This design is unimplemented. It must not change the already frozen monetary pilot or be presented as a measured result. The external behavior below is concrete enough to implement a reference and independent oracle; internal v2 schema and event choices should remain candidate-owned where compatibility permits.

## Business behavior and initial state

A tenant submits an integer credit to one of its accounts. The request is `{"op":"credit","tenant_id":str,"request_id":str,"account_id":str,"delta":positive_int}`. There are no insufficient-funds decisions, clock dependencies, or random IDs. The account exists, and caller authorization is supplied by the trusted workload. A read is `{"op":"balance","tenant_id":str,"account_id":str}`.

```sql
CREATE TABLE accounts (
  tenant_id TEXT NOT NULL, account_id TEXT NOT NULL,
  balance INTEGER NOT NULL,
  PRIMARY KEY (tenant_id, account_id)
);
CREATE TABLE requests (
  request_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL, account_id TEXT NOT NULL,
  delta INTEGER NOT NULL, operation_id TEXT NOT NULL UNIQUE
);
CREATE TABLE outbox (
  event_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL UNIQUE,
  version INTEGER NOT NULL, payload TEXT NOT NULL
);
```

The immutable v1 API looks up `requests` by `request_id` alone. Identical tenant/account/delta means an idempotent successful retry, with the original operation ID and no writes. Any mismatch returns `idempotency_conflict` with no business-state changes. A first request atomically inserts its ledger row, adds `delta` to the account balance, and appends one complete event. Its operation ID is the compact JSON string encoding `["legacy", request_id]`. Its event contains tenant, request, account, delta and operation ID. Its response is `{"ok":true,"operation_id":str}`. A balance read returns the exact tenant/account identity and balance.

The immutable v1 consumer returns one external credit instruction from that event, using its operation ID as the sink idempotency key. The sink records account, delta, logical `(tenant,request)` and key; it accepts repeated identical instructions, rejects key reuse for a different instruction, and never forgets an applied effect. The database balance and external credits are separate objects: both must be correct. Initial accounts, accepted legacy ledger rows, matching outbox rows, and any already applied external effects are declared input fixtures. The oracle derives initial balances/effects independently and checks fixture consistency before a run.

## Public migration behavior

There are three phases, controlled by the evaluator for the initial implementation:

1. `overlap`: v1 and v2 API calls and consumers can run. The global v1 uniqueness rule remains in force. V2 may not admit a cross-tenant reuse of a raw request key yet. V2 first admissions must be visible to an immediate v1 retry or rollback.
2. `retired`: no new v1 API requests or v1 consumer deliveries occur. Old events remain queued and can be delivered to v2 indefinitely. V2 now admits different tenants' identical raw request keys as distinct operations. Existing `(tenant,request)` pairs retain their original payload and operation IDs. Changed-payload retries still fail.
3. `complete`: the legacy globally unique ledger is removed, while all accepted requests, receipts, balances and old-event compatibility remain valid. New tenant-scoped traffic continues.

The phase rule is essential: unrestricted tenant collisions cannot be reconciled with an unchanged v1 API that searches only the raw key. A rollback returns to v1 only before the retirement barrier. It must not silently reenable v1 after a scoped collision has been admitted.

The scope of a logical request is `(tenant_id,request_id)` after retirement. Every pre-retirement accepted operation remains the same operation after migration. For a newly accepted post-retirement pair, v2 may choose any stable collision-free operation ID. The reference uses compact JSON `["tenant", tenant_id, request_id]`; this is a reference choice, not a mandatory internal algorithm. On the first valid response, the oracle binds that new logical pair to the returned ID only after checking that the ID is nonempty, unused for another logical operation, and represented consistently in the durable ledger/event. Repeated responses cannot rebind it. Legacy operation IDs are predetermined and cannot change.

Do not specify a new outbox payload layout beyond what the unchanged v1 consumers need during overlap and what the candidate's v2 consumer must interpret correctly. This leaves the API and consumer authors a real interface decision. The judge checks business effects and event immutability, not a preferred encoding. Preserve accepted outbox rows byte-for-byte throughout the migration.

## Callback interface and artifact boundary

The candidate submits `db.py`, `api.py`, and `consumer.py` plus an optional shared data-only interface manifest. All workers can inspect the full legacy source, all current candidate files and the public contract. No necessary input is hidden from a role.

```python
# db.py
expand(conn) -> None
backfill(conn, cursor: str | None, limit: int) -> {"cursor": str | None, "done": bool}
contract(conn) -> None

# api.py
handle(conn, request: dict, phase: str) -> dict

# consumer.py
consume(conn, event: dict) -> {
    "idempotency_key": str, "operation_id": str,
    "tenant_id": str, "request_id": str,
    "account_id": str, "delta": int
}
```

Consumers are read-only for this family: complete immutable events contain all necessary information. The sink is external and inaccessible except through returned instructions. Callbacks are serial atomic transactions in the first CPU demonstrator; no throughput/nonblocking claim follows. Globals or files are not persistent storage. Untrusted callbacks run outside the oracle process. The judge owns schedules, expected state, and effects.

To avoid prescribing the reference's internal scoped table name, expose a **read-only task-owned schema adapter declaration** for how to enumerate candidate accepted requests, or require a canonical SQL view with columns `tenant_id, request_id, account_id, delta, operation_id`. The view is an audit interface, not a source of expected answers: the oracle compares every row with its independent ledger. Define this before implementation. A canonical view permits multiple internal schemas without executing candidate Python inside the judge. Validate that querying it is bounded and read-only.

## Central reference strategy

Use a new `scoped_requests` table keyed by `(tenant_id,request_id)`, preserving account/delta/operation ID, plus a canonical audit view. Keep the v1 `requests` table authoritative for global conflict decisions until retirement. Lazy fallback to v1 is valid during partial backfill.

```text
expand:
    create scoped_requests and the audit interface

backfill(cursor, limit):
    scan at most limit legacy request rows by a stable key cursor
    insert each absent scoped row with its original immutable operation ID
    if a scoped row exists, assert exact payload/ID agreement; never replace it
    return the last scanned key and completion flag

handle(credit, overlap):
    inspect the legacy global request key
    if present: return original receipt iff full payload matches; else conflict
    otherwise atomically:
        choose legacy operation ID
        insert legacy and scoped rows
        update balance once
        append legacy-compatible complete event once
    return receipt

handle(credit, retired/complete):
    find scoped pair, falling back to a matching legacy row if still materialized
    if found: compare payload, return original receipt or conflict, change nothing
    otherwise atomically:
        choose a fresh tenant-scoped operation ID
        insert scoped row, add balance once, append complete v2 event once
    return receipt

contract:
    complete/reconcile remaining legacy aliases without rebinding any operation
    remove the legacy global-key table and expose all scoped rows to the audit view
    preserve old outbox rows, account balances and operation IDs

consume(event):
    decode its published version
    return its immutable identity/payload and original operation ID to the sink
```

New legacy requests inserted behind the backfill cursor cannot be missed: either a compatibility trigger populates their scoped rows or the completion pass restarts scanning and reconciles all legacy rows before removal. The reference should choose one strategy and test both partial-pass and restart schedules. A full final reconciliation is allowed unless a real bounded-work contract is separately implemented; do not pretend the cursor alone enforces online migration.

## Oracle and initial test matrix

For each first accepted logical request, the oracle records payload and identity exactly once; it advances the expected account balance exactly once. During overlap it additionally maintains the global key registry. It checks every response, canonical ledger row, balance and append-only outbox after each callback. Sink deliveries are independently checked against accepted logical requests and permanent effects. No event, receipt, or candidate view supplies the expected payload. Invalid syntax/protocol and infrastructure outcomes are distinguished from valid semantic failures.

Declare the following cases before any model call:

- Partial backfill, then v2 first admission, v1 retry and API rollback.
- A legacy retry after retirement while another tenant newly uses the same raw key.
- A delayed legacy event after that collision; its old ID must retain the old effect.
- Changed account/delta under an existing scoped pair; reject without balance or event changes.
- Keys containing quotes, separators, Unicode and strings resembling an ID prefix.
- Same account name in different tenants; no cross-tenant balance or receipt confusion.
- Lost sink acknowledgement and replay before and after contraction.
- Backfill restarts, newly inserted keys before the cursor, and receipts replayed from pre-migration state.

Reference must pass all cases. Controls must include regenerated legacy IDs (duplicate effect despite a clean scoped ledger), global dedupe retained forever (missing valid new tenant work), naive concatenated IDs (collision), and a conflict path that mutates then later repairs a balance (final pass/history fail). A no-migration reference can pass continuity but must fail required scoped-key progress. A correct offline conversion is a separate control, not a live-transition solution.

## Why this is not enough by itself

This is still a compact family with a conventional solution. Publishing its complete blueprint can make a specialized scaffold trivial. In the current pilot, the public API specifies most component choices, so each role can often implement independently; that tests code decomposition more than negotiation. This family should loosen internal schema/event representation while retaining precise external semantics, so workers must agree on actual shared choices and verify the combined result. Even then, teamwork is not assumed to outperform a central agent.

The stronger research target is whether a fixed-budget orchestration policy learns to identify cross-component compatibility obligations, request concrete interface agreements, select integration probes, and revise a joint implementation **on fresh migration families**. Compare with a strong central agent, a team with an explicit shared interface manifest and conventional expand/contract checklist, and a team with the same workers/tools but fixed verification cadence. Give all arms full information and normal coding tools. Freeze a family-disjoint split before optimization. Evaluate a learned scaffold against newly authored business semantics and legacy implementations; do not call renamed keys, shuffled schedules, or alternate numeric constants independent tasks. If a small hand-written protocol solves every family or strong baselines saturate, report that and abandon the claim of a challenging general benchmark.

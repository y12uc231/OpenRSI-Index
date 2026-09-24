# LiveMigrate demonstrator API

This is one order-service migration family with several deterministic traffic traces. Three workers implement `db.py`, `api.py`, and `consumer.py`. All workers receive this contract, the immutable v1 code, and all three starter files. Python 3.9 and the standard library are sufficient.

The task is to migrate integer `amount_cents` to integer `amount_micros` (1 cent = 10,000 micros), while v1 and v2 APIs and consumers coexist. During coexistence all amounts are divisible by 10,000 micros. After legacy retirement, arbitrary positive integer micros must work. A temporary API rollback to v1 can occur before retirement. Existing v1 code is immutable.

## Initial SQLite schema

```sql
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL,
  revision INTEGER NOT NULL
);
CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
  order_revision INTEGER NOT NULL, amount_cents INTEGER NOT NULL
);
CREATE TABLE outbox (
  event_id TEXT PRIMARY KEY, payment_id TEXT NOT NULL UNIQUE,
  version INTEGER NOT NULL, payload TEXT NOT NULL
);
```

The outbox is append-only: do not edit or delete previously accepted payment events. Payments are immutable snapshots of the accepted order revision and amount, not instructions to read the order's current amount later. There are no foreign keys. SQLite callbacks execute serially in real transactions; deterministic traffic is interleaved **between** callbacks, including between backfill chunks. This harness tests logical interleavings, not parallel database performance.

## Owned callback files

`db.py` defines:

```python
def expand(conn): ...
def backfill(conn, cursor, limit): ...  # -> {"cursor": int, "done": bool}
def contract(conn): ...
```

`expand` adds the micros representation and any compatibility mechanisms needed by both versions. `backfill` scans a bounded chunk of preexisting orders/payments; `cursor` starts at zero, `limit` is positive, and the returned cursor must progress until `done` is true. New writes can happen after a chunk was scanned. The runtime may restart a pass from zero. You may keep cents authoritative during overlap and reconcile micros before contraction; unused shadow fields need not be current, but every returned read and emitted payment snapshot must be correct. `contract` runs only after v1 retirement and all pre-retirement events have been delivered at least once; old events can still be replayed after contraction. It must preserve all orders and payment snapshots and remove `amount_cents` from both tables. Final schemas must contain the original identity/revision columns plus `amount_micros`; additional columns are allowed. You may create triggers and auxiliary tables. Do not commit, rollback, or close the supplied connection; the driver owns transactions. Callback processes may restart between invocations: persist state only in SQLite, not module globals or files.

`api.py` defines:

```python
def handle(conn, request, phase): ...  # -> JSON-safe dict
```

`phase` is `overlap` or `v2_only`. Requests are:

- `{"op":"put","order_id":str,"expected_revision":int,"amount_micros":int}`. Create uses expected revision 0. Update uses the current revision. Return `{"ok":true,"revision":expected_revision+1}`. A revision conflict must return `{"ok":false,"error":"revision_conflict"}` and change nothing.
- `{"op":"get","order_id":str}`. Return `{"ok":true,"order_id":str,"revision":int,"amount_micros":int}`.
- `{"op":"pay","payment_id":str,"order_id":str,"expected_revision":int}`. Atomically insert an immutable payment snapshot and outbox event. Return `{"ok":true,"payment_id":str}`. A retry with the same payment ID and identical request must succeed without adding another event. Reusing an existing payment ID with a different order or expected revision returns `{"ok":false,"error":"idempotency_conflict"}` and changes nothing, even if the new order revision is valid. Both v1 and v2 have this behavior. A new payment with an incorrect order revision must return the same revision-conflict response and change nothing.

Use `event_id = payment_id`. Emit version-2 JSON payloads containing at least `payment_id`, `order_id`, `order_revision`, and `amount_micros`. During overlap include the exact `amount_cents` projection as well, so the unchanged v1 consumer can process the event. The v1 consumer ignores extra fields and version tags. After retirement this legacy projection is unnecessary. During overlap v2 writes must remain readable and writable by the unchanged v1 API. The v1 API uses otherwise identical request semantics with `amount_cents` instead of `amount_micros` and emits version-1 payloads with cents only.

`consumer.py` defines:

```python
def consume(conn, event): ...  # -> settlement dict
```

`event` is `{"event_id":str,"payment_id":str,"version":1|2,"payload":dict}`. The connection is read-only for this callback. Return `{"payment_id":str,"idempotency_key":str,"amount_micros":int}`. Read the immutable event snapshot; support both versions. The trusted sink applies a charge once per idempotency key, rejects reuse with a different payment or amount, and retains all physical effects. Therefore all deliveries of a payment, including those spanning old/new consumers, must use `idempotency_key = payment_id`, as the immutable v1 consumer does. The driver can replay an event after a successful charge whose acknowledgement was lost. Consumers cannot write the settlement ledger.

## Required behavior and evaluation

The driver calls expansion, multiple interleaved backfill chunks, mixed v1/v2 requests and delayed/replayed event deliveries, an optional v1 rollback interval, a final backfill pass, contraction, and new micros-only traffic. Acknowledged writes, reads, payment snapshots, and settlement effects are checked against an independent logical request ledger. Conflicts must not produce effects. Existing outbox rows must not be modified. Final cleanliness cannot repair an earlier incorrect read, acknowledgement, missing snapshot, or external charge.

`runtime.execute(candidate_dir, scenario, invoke=None)` returns JSON-safe `static`, `trace`, and `completion` reports plus an overall pass flag. `python runtime.py --candidate starter --suite public` runs public smoke; `--candidate reference --suite heldout` validates the reference locally. The default invoker loads Python callbacks in process and is **only for trusted reference/tests**. An isolated pilot must supply an RPC invoker or run the whole harness in a no-network disposable container. A whole-harness container contains the oracle, so it is an honest-code demonstrator, not an adversarially secure evaluation. The supported dispatch hook is `invoke(role, function, conn, *args)`, with role one of `db`, `api`, `consumer`; the SQLite connection is backed by an on-disk temporary database. No expected ledger or settlement sink is passed to callbacks.

The public scenario and held-out trace variants share one published contract. They are not claimed to be separate migration families. No model difficulty claim follows from reference or bug-control results.

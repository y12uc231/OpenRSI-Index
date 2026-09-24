# Identity migration: public contract

This family follows `REQUEST-ID-BLUEPRINT.md` from the LiveMigrate research design. It is separate from the cents-to-micros instrument pilot. Its pilot protocol and source are frozen before its model calls.

Three workers own `db.py`, `api.py`, and `consumer.py`. All receive this contract, immutable v1 source, all starter files, and peer implementations. Implement with Python 3.9 and SQLite. The driver supplies the phase schedule; this task generates compatible service code, not deployment decisions. Callback processes may restart: persistent state belongs in SQLite. The driver owns transactions; do not commit, roll back, or close its connection. Consumers receive a read-only connection.

## Initial schema and behavior

```sql
CREATE TABLE accounts(tenant_id TEXT NOT NULL,account_id TEXT NOT NULL,
 balance INTEGER NOT NULL,PRIMARY KEY(tenant_id,account_id));
CREATE TABLE requests(request_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,
 account_id TEXT NOT NULL,delta INTEGER NOT NULL,operation_id TEXT NOT NULL UNIQUE);
CREATE TABLE outbox(event_id TEXT PRIMARY KEY,operation_id TEXT NOT NULL UNIQUE,
 version INTEGER NOT NULL,payload TEXT NOT NULL);
```

Accounts and request inputs are trusted, and requested accounts exist. Credits use positive integer deltas. The legacy API atomically increments the account balance, inserts one request ledger row, and appends one complete event. Its globally unique request key is `request_id`. Identical tenant, account, and delta under the same key is a successful retry with no new writes; any mismatch returns `{"ok":false,"error":"idempotency_conflict"}` without changing business state. Its operation ID is the compact JSON string encoding `["legacy", request_id]`, with `ensure_ascii=False` and separators `(',', ':')`.

Old operation IDs and outbox rows must remain unchanged forever. The external credit sink is independent of the database balance: both must be correct. A sink delivery can be repeated after a lost acknowledgement.

## Phases and API

`api.handle(conn, request, phase)` returns a JSON-safe dictionary. `phase` is `overlap`, `retired`, or `complete`.

- During `overlap`, unchanged v1 and new v2 writers and consumers coexist. Global request-key uniqueness still applies. Every first admission by v2 must be visible to a subsequent v1 retry or rollback. Accepted IDs use the legacy encoding.
- After `retired`, no v1 API calls or consumers run, but old queued events and retries remain valid. Distinct tenants may now reuse a raw request key. Existing `(tenant_id,request_id)` pairs retain their accepted payload and operation ID. For a genuinely new pair, v2 chooses any stable nonempty operation ID not used by another accepted logical operation. Encoding/layout is a candidate design choice, not a reference implementation requirement.
- In `complete`, the legacy `requests` table has been removed; the scoped ledger and continuing traffic remain correct.

Credit request: `{"op":"credit","tenant_id":str,"request_id":str,"account_id":str,"delta":positive_int}`. Successful first admission or identical retry returns `{"ok":true,"operation_id":str}`. A changed account or delta for an existing pair returns the conflict response and changes nothing. Balance request: `{"op":"balance","tenant_id":str,"account_id":str}` returns `{"ok":true,"tenant_id":str,"account_id":str,"balance":int}`. Scalars must have their specified JSON types; booleans are not integer amounts.

Each accepted logical operation has exactly one durable outbox row with its operation ID. Event IDs are stable unique strings chosen by the implementation. During overlap, v2 events must include the legacy payload fields `tenant_id`, `request_id`, `account_id`, `delta`, and `operation_id` so the unchanged v1 consumer works. After retirement, candidate API and consumer may agree on any payload representation and version tag, including an operation-ID reference to a preserved immutable accepted record. Previously accepted outbox rows are append-only and preserved byte-for-byte.

## DB and audit interface

```python
def expand(conn): ...
def backfill(conn, cursor, limit): ...  # {"cursor": str|None, "done": bool}
def contract(conn): ...
```

Expansion must preserve the legacy schema and create a SQL view named `accepted_requests`, with columns `tenant_id,request_id,account_id,delta,operation_id`, enumerating each accepted logical operation exactly once. A view combining old and new stores is valid during backfill. This is an audit interface, not expected answers: the judge compares it to its independent request ledger. Internal tables and indexes are candidate-owned. Backfill starts with cursor `None`, uses positive `limit`, and returns JSON progress state. A nonterminal call must change the cursor; a pass must finish within 64 callbacks in these small traces. New legacy keys may appear behind the cursor; the driver can restart a pass. Full final reconciliation is allowed. No bounded-work or nonblocking-performance claim is made.

`contract` runs after retirement, when scoped collisions may already exist. It removes the legacy `requests` table, preserves all accepted identities/payloads/balances/outbox rows, and leaves `accepted_requests` intact. Do not retain global uniqueness under another table as an admission rule: newly valid scoped work must still succeed.

## Consumer and independent sink

`consumer.consume(conn,event)` receives `{"event_id":str,"operation_id":str,"version":int,"payload":JSON_value}`. It returns:

```json
{"idempotency_key":"...","operation_id":"...","tenant_id":"...",
 "request_id":"...","account_id":"...","delta":1}
```

The external sink identifies the logical operation by `(tenant_id,request_id)`. Both `operation_id` and `idempotency_key` must equal that operation's permanent accepted ID. Repeating the exact instruction applies no additional credit; reusing a key for a different instruction is a violation. Use immutable event information or a uniquely identified immutable accepted record, not the account's latest state or an ambiguous global key lookup. The v1 consumer uses its event's original operation ID. V2 must still interpret delayed v1 events after legacy-table removal.

## Driver, oracle, and scope

`runtime.execute(candidate_dir,scenario,invoke=None)` emits JSON-safe static/trace/completion diagnostics. `runtime.py --candidate reference --suite all` validates trusted reference code. Its default in-process invoker is only for trusted references/tests, not an untrusted-code sandbox. A generated-code pilot must use a separate-process/container invoker with the same `invoke(role,function,conn,*args)` hook. The supplied SQLite connection is file-backed and has no open host transaction at dispatch; external invokers must commit before returning. The oracle ledger and permanent sink are not stored in the candidate database or passed to callbacks.

The judge derives accepted payloads/balances from requests, checks responses and canonical ledger/account state after every callback, preserves outbox-history checks, and checks every physical external effect. For a new post-retirement operation it binds a candidate-selected ID only if nonempty, unused for a different pair, and consistent with the durable ledger and outbox. Final repair cannot erase earlier incorrect business state or effects. Syntax/import/callback exceptions are `candidate_invalid` and unscored; completed semantic failures score zero. Marked infrastructure failures propagate unscored.

Three held-out trace variants remain one identity-migration family. The public contract intentionally leaves the scoped schema and post-retirement event encoding to the collaborating workers. Difficulty, novelty, and team benefit remain unmeasured.

# Reservation ownership migration draft

This is a specification-first research draft, not a measured benchmark. Three author roles implement `db.py` (source bridge/handoff), `api.py` (bundle gateway), and `consumer.py` (new owner). Each defines `on_message(conn, message)`. The consumer module runs independently at owner A and owner B; gateway, source, A, and B each have a separate durable SQLite database. They cannot read or write one another's files. All authors receive the entire public contract, immutable legacy source, and peer code.

## Business behavior

The operation is `reserve_bundle(reservation_id, lines)`, where IDs are nonempty strings and `lines` is a nonempty map from published SKU strings to positive integer quantities (booleans are not integers). It atomically commits every requested line, or returns `out_of_stock` without consuming anything. This first version has no user cancellation after commit. Temporary prepared holds are internal protocol state, not completed reservations. Identical retries return the original result without another effect. Changed payload under an existing reservation ID returns `idempotency_conflict` without changing its accepted reservation. The ID namespace is global across all SKUs and both legacy/v2 entry points, including requests first admitted after a handoff.

Successful completion causes one external fulfillment for the entire bundle, durably deduplicated by reservation ID. Database repair cannot erase that effect. A committed reply requires either all lines durably committed, or a durable irrevocable global commit decision with every line durably reserved as prepared/committed under the same identity. Standard two-phase commit may acknowledge after this global decision before participant acknowledgements arrive. All participants must eventually finish under fair recovery; reserved obligations cannot disappear meanwhile. Different concurrent reservations may legitimately have different winners; the judge accepts any linearizable history under these semantics and real-time client ordering.

The initial legacy service owns X, Y, and Z. Migrate X to A and Y to B while requests run. Z remains on the source. The source bridge gates old writes and preserves old receipts; an immutable legacy engine need not directly mutate a partially migrated distributed bundle. It can defer a legacy request while relevant tentative holds exist, or route the unchanged public request through the new gateway once a requested resource is fenced.

## Process and message interface

Each callback receives `message = {"src": authenticated_node_or_driver, "body": JSON_object}`. Driver messages are public:

- `init`: includes `node_id`, initial routing, and the published SKU capacities.
- `client`: includes `call_id`, `reservation_id`, and `lines`. The source receives legacy client calls; the gateway receives v2 calls.
- `move`: sent to source with `sku` and `destination`, requesting a handoff.
- `tick`: a fair opportunity to retry outstanding work from durable state.
- `reply_ack`: includes `call_id`; the external client observed this reply. It is sent to the replying node and original receiving node if those differ. Lost acknowledgements are recovered by repeating a durable reply.

The exact node IDs are `source` (db.py), `gateway` (api.py), `A` and `B` (independent consumer.py instances). Each initially receives:

```json
{"src":"driver","body":{"kind":"init","node_id":"A","capacities":{"X":3,"Y":3,"Z":2},"routing":{"X":"source","Y":"source","Z":"source"}}}
```

Substitute the receiving node's ID for `A`. Example external messages are `{"src":"driver","body":{"kind":"client","call_id":"c1","reservation_id":"r1","lines":{"X":1,"Y":1}}}`, `{"src":"driver","body":{"kind":"move","sku":"X","destination":"A"}}`, `{"src":"driver","body":{"kind":"tick"}}`, and `{"src":"driver","body":{"kind":"reply_ack","call_id":"c1"}}`. Only driver messages require this `kind` vocabulary; candidate internal bodies can use a different encoding. The complete friendly public traffic schedule is also in `PUBLIC_SCENARIO.json`.

Callbacks return `{"messages":[{"to":node_id,"body":JSON_object}],"replies":[{"call_id":str,"reservation_id":str,"status":"committed"|"out_of_stock"|"idempotency_conflict","lines":object}]}`. A role may return empty lists. Internal message formats and identifiers are agreed by the candidate team; the judge does not require the reference's wire protocol. Sender identity cannot be forged. Replies must correspond to invoked calls and requested payloads. Source and gateway can produce client replies; owners cannot directly bypass the client gateway.

Callbacks run as atomic local transactions. Do not commit, roll back, or close `conn`; the dispatcher owns it. The driver may drop outgoing messages or replies after local state commits, modelling a process crash before buffered sends/acknowledgements are observed. One tested fault drops the first nonempty source output batch after its X authority is independently observed as fenced, regardless of which callback performed the handoff; another applies a committed fulfillment but loses its first gateway reply and acknowledgement. Later ticks and repeated delivery must recover from durable state. The network may reorder and duplicate messages. Identical queued `(sender,destination,body)` packets are coalesced until delivered; applications cannot depend on their multiplicity. Every callback can start a fresh Python process; globals/files are not durable state. The fault prefix is finite. During the recovery suffix all nodes run, no new messages are dropped, and queued messages and ticks are scheduled fairly. No completion is demanded during a permanent partition or permanent loss of durable state.

All physical fulfillment deduplication is external and retained even if a reply acknowledgement is lost. A replayed correct committed reply is harmless; changing its bundle is a violation.

## Source storage and immutable engine

The trusted initial schema contains:

```sql
CREATE TABLE legacy_stock(sku TEXT PRIMARY KEY,total INTEGER NOT NULL,
 available INTEGER NOT NULL,epoch INTEGER NOT NULL,active INTEGER NOT NULL);
CREATE TABLE legacy_holds(reservation_id TEXT NOT NULL,sku TEXT NOT NULL,
 qty INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(reservation_id,sku));
CREATE TABLE legacy_requests(reservation_id TEXT PRIMARY KEY,
 fingerprint TEXT NOT NULL,status TEXT NOT NULL,lines_json TEXT NOT NULL);
```

Source protocol preparation must deduct from `legacy_stock.available` and record holds in the same source transaction, so the unchanged legacy engine sees reserved capacity. A legacy request overlapping an unresolved tentative hold must be deferred or routed appropriately, not permanently rejected just because a prepare may later abort. Identity/receipt lookup occurs before availability checks. New holds must not be created on a fenced source SKU.

The published immutable helper provides `reserve(conn, reservation_id, lines) -> {status,lines}` via `import legacy`. It atomically checks the legacy request ledger, rejects changed payload, commits all-source lines if available, records committed holds and the durable receipt, or records a justified out-of-stock receipt. Source code receives only this read-only public helper inside its sandbox; no judge or reference directory is exposed. The initial source rows have `total=available=capacity`, `epoch=0`, `active=1`; its other tables are empty. Other nodes begin with empty databases. Python module monkeypatching is not a hardware immutability guarantee; editing/replacing the published helper is outside the authoring interface.

## Auditable state without mandated private table layouts

Each source/owner database exposes two SQL views after `init`:

```text
audit_inventory(sku,total,available,epoch,authority)
audit_holds(reservation_id,sku,qty,state)
```

Gateway exposes `audit_decisions(reservation_id,lines_json,state)`, where `lines_json` is the JSON object for the accepted request and `state` is `commit` or `abort`. This view may be empty for an implementation that uses the all-participants-committed certificate. Once exposed, terminal decisions must remain with the same payload and state; duplicate IDs are invalid. A commit decision requires every line already durably reserved. The gateway's private storage need not resemble a reference coordinator table.

`authority` is `active`, `staged`, or `fenced`; hold state is `prepared`, `committed`, or `released`. Source views project the legacy tables consistently. Target private tables, indexes, protocol journals, and message payloads are candidate choices. Gateway persistence is also candidate-owned. Views are bounded read-only audit interfaces, not expected answers; the judge independently owns initial capacities, client inputs, observations, and effects.

For each local resource snapshot, available capacity plus prepared and committed holds equals its original total, and all quantities are nonnegative. Only one node may be active for a SKU. Staged transfer copies do not create additional active stock. A temporary interval without an active owner is allowed during a correct fence/activation handoff. An active new owner must use a strictly newer epoch than the source, which must already be fenced. Replays cannot reopen a prior authority epoch. Previously committed holds must survive handoff under their original reservation and line identity.

Completion requires X active only on A, Y active only on B, source authority for X/Y fenced, all client calls resolved, every committed bundle fulfilled once, all committed participant work finished, and a linearizable client history. Z must make progress within the published 10-round stable window even while messages from A to gateway are delayed. New satisfiable X/Y work must finish within a later 20-round window with source paused. Affected bundles may stay pending until recovery. Deferring a handoff until relevant tentative holds finish is valid; copying unresolved prepared holds is not mandatory.

The declared schedules have eight client calls and 113 rounds with deterministic delivery priorities and ticks. Bounds are 6,000 total callbacks, 2,000 distinct queued packets, at most 100 inventory/decision rows and 500 hold rows per audit projection, 1 MiB per SQLite value/row, 2 MiB returned per audit query, and 2 million SQLite VM steps per query. The independent history checker supports up to 12 client calls and 100,000 memoized states. Exceeding checker/SQL bounds is explicitly unscored, never silently called an exhaustive failure; invalid code, callback exceptions and protocol/work-bound violations are reported as candidate-invalid with no numeric score. A complete semantically incorrect execution scores zero. These are generous execution limits, not a formal guarantee for arbitrary algorithms.

## Evaluation and implementation scope

The runtime is `execute(candidate_dir, scenario, invoke=None)`. Isolated invokers dispatch `invoke(role, "on_message", conn, message)` on the correct node's file-backed connection with no open host transaction. The default loader is for trusted reference/tests only. Isolated evaluation requires a host Python 3.11+ providing SQLite `setlimit`; trusted reference tests may also run under older Python. The source helper is supplied as its own published immutable sandbox artifact, not imported from a host reference path. Judge history and other nodes' databases must never be mounted.

The judge checks resource/authority state and committed obligations after each callback, and checks every client reply against current commitments and permanent effects. A bounded independent linearizability search accepts any legal winner among concurrent reservations; it does not enforce the reference's schedule. Fair-recovery completion is separate from safety. Invalid code/protocol and infrastructure outcomes are reported separately from completed semantic failures.

The four declared causal schedules cover prepared-hold transfer, delayed/replayed decisions, lost output after durable commit, interleaved X/Y transfers, partial-bundle abort and release, changed-payload retries across entry points, and independent Z traffic. They do not exhaustively explore distributed message schedules. The exact bounded search checks only each observed client history. Alternate wire/schema, drain-before-transfer, and early-acknowledgement regression controls are included. Reference validation establishes solvability and checker sensitivity; it provides no evidence yet that current models fail this task. An initial six-call tool-free model pilot would be a feasibility experiment under this authoring interface, not a general claim about full coding agents.

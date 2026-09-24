# What to build after the instrument pilot

The implemented cents-to-micros migration is one semantic family. Its public trace and three held-out trace variants validate a deterministic evaluator and illustrate the difference between final state and execution history. They do not establish benchmark breadth, frontier-model difficulty, coordination gains, or a novel research method. The driver supplies the rollout schedule; the current workers generate compatible code, rather than deciding when to deploy versions.

The next step should be a second family with a different semantic obligation, before adding more order-service names, amount scales, or traffic permutations. The detailed designs in [NEXT-FAMILIES.md](NEXT-FAMILIES.md) provide two candidates.

| Extension | Distinct obligation | Extra harness machinery | Recommendation |
| --- | --- | --- | --- |
| Global retry keys to tenant-scoped identities | Preserve the original canonical effect identity across a change of uniqueness scope while admitting newly legal work after retirement | A scoped ledger, canonical identity oracle, signed-account sink | Implement next: fits the current three-worker shape and immutable consumer-effects interface |
| Atomic reservation event to allocation and confirmation fragments | Preserve causal prerequisites and inventory conservation at every effect prefix while fragments arrive out of order | Durable candidate consumer inbox, ordered action batches, stateful inventory sink | Implement after the identity family; first extend consumer persistence and sink semantics explicitly |

## Recommended next implementation: identity continuity

Keep DB, API, and consumer as real independently owned Python modules, with all contracts shared. The DB worker implements backfill and compatibility aliases; the API worker enforces the correct admission rule and atomically writes ledger/outbox records; the consumer worker retains the canonical effect identity of each operation. A legacy request accepted with key `k` must remain the same operation when retried through the new API after retirement. A different tenant may then legitimately use `k` for a different new operation.

The hard boundary is specified rather than hidden: while unchanged v1 code can still handle requests, keys remain globally unique. Scoped collisions become legal only after retirement. Old accepted operations keep legacy effect IDs permanently; new post-retirement operations receive a disjoint, structured scoped ID. The protocol publishes the encoding so ordinary string-delimiter accidents do not become an unspecified puzzle.

A minimal demonstration has three accepted operations: tenant A's legacy operation `k`, its retry through v2, and tenant B's new post-retirement operation also named `k`. A delayed legacy event and a lost-ack replay surround that transition. A migration that assigns the original operation a fresh scoped ID can pass final ledger/schema checks but apply it twice. A migration that keeps global deduplication forever avoids duplicates but incorrectly rejects tenant B's valid new operation. The oracle checks both preservation and progress; merely refusing work cannot pass.

Before model evaluation, require a reference that passes all declared traces and at least these two negative controls. Add a changed-payload retry and a key containing delimiter-like text to verify payload binding and the published encoding. These should be declared before observing model outcomes. More independent traffic traces improve coverage, but remain one family.

## Harness boundary for multiple families

Do not expand the current order-specific `expected_request` with a growing list of mode flags. Give each family a trusted specification module implementing initial schema/state, immutable legacy callbacks, traffic generation, request transition rules, observable state projections, and external-effect interpretation. A common driver owns callback isolation, transactions, action scheduling, failure classification, and persistent trace violations. Candidate-facing API contracts can differ where the semantics require it; do not force the fragment family into the current read-only consumer callback.

The judge must remain independent of candidate state. It derives accepted logical operations from the prescribed request stream, owns canonical identities and external effects, and checks snapshots after every callback. Candidate code can inspect its real working database and published event history but cannot modify judge ledgers. A completed semantic failure receives the declared finite score; invalid candidate execution and infrastructure failure remain separately reported and unscored under the pilot protocol.

The existing runtime has not yet been refactored into this family interface. No new family is implemented by this note.

## What the outer research agent would optimize

A substantive outer research artifact is a reusable team workflow that chooses shared contract checks, cross-role evidence to exchange, integration tests, and repair allocation under a fixed budget. Frozen DB/API/consumer workers then solve each new migration instance using that workflow. The workflow should not contain the reference implementation for each family or recognize held-out case IDs.

Compare it with a conventional compatibility checklist, periodic integration with shared peer code, a strong centralized agent receiving all specifications, and a serial implementation control. Count all worker, coordinator, test-generation, and repair inference. The current six-call feasibility pilot is a diagnostic with differing team and central scheduling; it is not a token-matched scientific comparison.

For an RSI study, fix the family split before running the outer search. Development feedback must come from development families; final judging should use fresh authored semantic families and schedules not available to workflow development. Three hand-authored families alone are insufficient evidence of broad software generalization. If a standard scaffold or centralized control solves all declared tasks, report that result and reassess the research target rather than claiming difficulty from weaker workers or selectively adding failure cases.

Neither extension is claimed novel here. Its exact capability and closest prior benchmarks still require a separate primary-source novelty audit before submission.

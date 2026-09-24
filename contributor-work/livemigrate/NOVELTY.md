# Research audit: correctness during a live migration

Research cutoff: 2026-09-23. This direction was selected from current external
research, independently of the contributor's earlier work. It is a candidate
evaluation contribution, not a claim that live migration itself is new.

## Question

Can a team of coding agents change a stateful application's data and event
contracts while old and new components coexist, without violating any
externally acknowledged operation during the transition?

The important distinction is the object being graded: the **entire externally
observable execution**, including intermediate mixed-version states. A final
correct database and passing tests cannot undo an earlier incorrect settlement.

## Nearest work and limits of the claimed gap

| Primary source | What is already covered | Distinction to test here |
| --- | --- | --- |
| [SWE-Chain, May 2026](https://arxiv.org/html/2605.14415v1) and [code](https://github.com/CUHK-ARISE/SWE-Chain) | Consecutive package upgrades, regression preservation, inherited code changes; target-version tests after each step. | Live traffic across simultaneously active component versions, including externally visible failures that disappear from the final snapshot. |
| [SWE Refactor Bench, August 2026](https://arxiv.org/abs/2608.23564) | Whole-repository migration completeness, behavioral tests, and agent-generated tests for hidden differences. | Prefix correctness of the deployment execution, rather than only the migrated artifact. |
| [Continuous Benchmark Generation, November 2025](https://arxiv.org/html/2511.10049v1) | Enterprise service-platform migration, heterogeneous source/config changes, intent/reference-patch based benchmark construction. | Executed mixed-version data-contract migration with an independent operational history oracle. |
| [CoAgent, June 2026](https://arxiv.org/html/2606.15376v1) | Concurrent tool-using agents, live Kubernetes remediation and canary release, semantic conflict detection and compensation. | Correctness of code-generated schema/event migration for every acknowledged application operation; compensation cannot erase observed incorrect effects. This is a narrow distinction, not a claim that multi-agent concurrency is unstudied. |
| [DBA-Bench, July 2026](https://arxiv.org/html/2607.22165v1) | Database operations under active workloads, integrity, continuity and safety. | Jointly changing API, storage and asynchronous consumer implementations, with exact semantics for both old and new events. Database continuity by itself is not novel. |
| [DEC Bench migration assertions](https://github.com/514-labs/agent-evals/tree/a6748e5512f82d6f7e4b3688e0ae3d75339c5ce7/scenarios/foo-bar-clickhouse-live-schema-migration/assertions) | Real ClickHouse migration, data/backfill checks, and post-migration queries; other scenarios include post-migration write probes. | The four inspected migration/evolution scenarios grade final state and fresh probes after agent completion, not an immutable history of application acknowledgements throughout component transition. |
| [TeamBench](https://teambench.github.io/) | Explicitly advertises multi-step migration, zero-downtime cutover, schema evolution and DB migration coordination tasks. | Requires source-level comparison of its actual tests. Merely combining agents and migration is NOT a novelty claim. |
| [ConsequenceBench](https://github.com/yuvin-labs/consequencebench) | Ambiguous commits, late effects, recovery, compensation, shared-resource races and legitimate-effect preservation. | Candidate-created compatibility code and event semantics across software versions, rather than generic operational recovery. |

This search cannot establish that an idea is absent everywhere. The defensible
claim is a specific, executable evaluation design and a documented comparison
with the nearest public systems. A matching released task and equivalent oracle
would invalidate the claimed gap.

The [DBA-Bench artifact tree at the inspected commit](https://github.com/TanJI-C/DBA-Bench/tree/7b27b5d608ce3df9b26f9aee8f181b48d7269259)
contains only a release-placeholder README. Its paper remains close prior art;
the unavailable fixtures do not establish absence of an equivalent oracle.

## Directions rejected during this search

- Generic distributed-information teamwork: [HiddenBench](https://github.com/Yassellee/HiddenBench_ICML)
  and [SILO-BENCH](https://aclanthology.org/2026.acl-long.1354/) already target it.
- Teammate replacement: [Testing Interchangeability in LLM Agent Teams](https://arxiv.org/abs/2609.05279)
  already evaluates role-matched agent replacement.
- Generic selective verification: [Sherlock](https://arxiv.org/html/2511.00330v1)
  already learns verification placement, uses speculative execution and selective rollback.
- Generic failure recovery: ConsequenceBench and [RAC](https://arxiv.org/html/2605.03409v1)
  make a simple retry/rollback benchmark insufficiently distinct.
- Generic active causal discovery with calibrated sensors: CausaLab, ACDB,
  CausalDS and newer multi-instrument discovery work are too close to claim that
  adding several laboratory agents creates a new evaluation capability.

## Three concrete tasks in the proposed family

1. **Change monetary representation while orders keep changing.** A legacy API
   writes integer cents. A new API and consumer use integer micros. Backfill
   overlaps updates; delayed jobs refer to earlier accepted revisions. Grade the
   exact revision and amount of every settlement, not merely final row values.
2. **Repartition an idempotency ledger during retries.** A legacy service dedupes
   by a global request key; the new system scopes keys by tenant. Old retries and
   delayed acknowledgements cross the cutover. Grade exactly-once effects and
   rejection of payload-changing retries. This is a planned task, not implemented
   evidence.
3. **Split one event contract into two dependent events.** Old consumers expect
   one atomic reservation; new services consume allocation and confirmation
   separately. Deploy and roll back while messages are delayed and replayed.
   Grade conservation of inventory and absence of premature confirmations. This
   is a planned task, not implemented evidence.

The initial demonstrator implements only task 1. Different traffic schedules
within that task are stress cases, not independent task families.

## Difficulty and rejection criteria

No score from another benchmark is evidence of low model performance here.
The first local Codex pilot is a feasibility and failure-discovery experiment;
it cannot establish that most models fail. Publish every preregistered result,
including full successes. Do not increase difficulty after observing a model's
failure and then report it as a held-out comparison.

Before a substantive benchmark claim, require:

- A reference implementation that passes the same operations and budgets.
- Negative controls that pass static/final-artifact checks but fail temporal
  checks, including a final-state repair that cannot repair the history.
- A centralized agent with the same available information and total inference
  allowance; a serial coordination control; and an explicit compatibility
  contract / expand-contract baseline.
- A no-migration control and an all-new offline control, to separate ordinary
  coding failures from transition-specific errors.
- Fresh independently authored migration families. If a single generic
  boilerplate patch solves all tasks without understanding their contracts,
  reject the claim of a broad challenging evaluation.

The CPU simulator makes testing cheap and reproducible. It does not by itself
establish fidelity to PostgreSQL locks, actual network timing, Kubernetes,
production throughput, or arbitrary distributed schedules.

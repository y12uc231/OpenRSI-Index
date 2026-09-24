# LiveMigrate: can coding agents preserve a running system's promises?

**A new evaluation prototype, not an established benchmark or a demonstrated
frontier-model weakness.** This contribution was developed from a fresh audit of
current external work. It does not extend the contributor's older research.

The [original pilot results](results/README.md) are all successes: local
`gpt-6-astra` at `ultra` passed the first two families in both team and centralized
modes; it also passed the third family in both modes, as did `gpt-6-sol` in team
mode. The examples validate the instrument but do not meet a high model-difficulty
bar. Separate exploratory concurrency results must not replace those original scores.

**Retired as the main high-difficulty proposal on 24 September 2026.** A final
[20-seed diagnostic](results/seeded-reservation/README.md) yielded 20/20 passes
for both Astra implementations and 19 passes plus one unscored invalid execution
for Sol. The retained evidence does not support the intended broad difficulty
claim. No further task complexity is being added to force model failures.

Three coding agents own different parts of a live migration. Their code must
agree on durable identities, authority and recovery while old and new components
coexist. A trusted driver supplies the rollout requests and traffic; agents
implement the cooperating services and their protocol.

The main new family is [reservation ownership migration](families/reservation/README.md).
An order needs stock from two SKUs. Their ownership is moving from a legacy
service to two separate owners. A message disappears after durable state changes;
an acknowledgement is lost after fulfillment; a client retries. The team must
preserve atomic reservations and original receipts, finish both transfers and
keep unrelated stock usable. Each of the four services has its own database.

The research question is whether a reusable coordination policy helps fixed
coding workers preserve these cross-component obligations. It is not whether
the task introduces a new distributed transaction algorithm. A conventional
sequential team and a centralized author are declared controls.

## The failure this measures

A system can fulfill an order before every stock owner has a durable obligation,
temporarily activate two owners, or block unrelated orders throughout a transfer.
It may later reconcile to a correct-looking database. The earlier amount family
demonstrates the same problem with a stale $10 payment after a legacy update to
$15: final repair cannot undo the externally visible action.

The evaluator records client calls, irreversible effects and state violations
outside candidate code. The reservation family adds a bounded exact
linearizability checker that accepts any legal concurrent winner. It also
requires progress and completed ownership transfer, so refusing work or retaining
the old authority forever does not pass.

## What is new, and what is not

Migration, expand/contract, multi-agent SRE, and temporal safety checks all have
substantial prior art. The proposed contribution is the combined executable
contract: **joint service changes, legacy receipts, separate durable owners,
interleaved transfers, permanent external effects and operation-history grading**.

The [source-level audit](PRIOR-ART-AUDIT.md) compares actual TeamBench and related
graders; the [current update](PRIOR-ART-UPDATE.md) includes recent distributed
debugging, agent protocols and migration research. The [research note](NOVELTY.md)
records alternatives and rejection criteria. This is a bounded novelty claim,
not proof that no similar idea exists anywhere.

## Current scope

Three semantic families are implemented: order amounts change from integer cents
to integer micros; [request identity](families/identity/README.md) changes from
global keys to tenant-scoped keys while preserving legacy retries and effects.
The third, [separate-owner reservations](families/reservation/README.md), moves
atomic bundle reservations across four durable services under lost/replayed
messages, concurrent ownership transfers, and continuing legacy traffic.
Each family has one public and three held-out traffic traces. These schedules
are not advertised as independent tasks. See the separately declared
[reservation pilot](pilot/RESERVATION-PROTOCOL.md).

- [API contract](API_CONTRACT.md): complete public specification.
- `starter/`: three unfinished role modules.
- `reference/`: conventional correct implementation for evaluator validation.
- `runtime.py`, `scenarios.py`: trusted deterministic SQLite driver and oracle.
- `isolated.py`, `candidate_driver.py`: candidate execution across a process and
  Docker boundary; the expected history is not mounted into candidate containers.
- [Pilot protocol](pilot/PROTOCOL.md): model, calls, visibility, accounting and
  reporting rules fixed before local inference.

The [independent checker cross-check](diagnostics/history_crosscheck.py) compares
the memoized history oracle with full permutation enumeration on 2,000 seeded
histories of up to five calls: 218 linearizable, 1,782 non-linearizable and zero
disagreements. This is a reproducible finite validation, not a formal proof.

The environment is CPU-only and uses Python's standard library. It deliberately
does not claim to simulate PostgreSQL locking, production latency or arbitrary
network schedules. The deterministic scheduler interleaves real SQLite callback
transactions and workload operations.

## OpenRSI research task

The evaluation is the measurement instrument. The proposed **research task** is
to improve the coordination and review scaffold around fixed coding workers:
form a hypothesis, change how agents agree on cross-version contracts, generate
the three modules, evaluate, inspect bounded feedback, and revise the scaffold.
The optimized artifact is the reusable scaffold, not a hard-coded solution to
one published cents-to-micros example.

The [declarative research lane](research/README.md) now implements that artifact
and a fixed-controller evaluation command. It includes a conventional
contract-first reference policy and a [pinned current open-model lane](compute/README.md).
GPU execution and the Harbor integration remain unvalidated.

This three-family demonstrator can validate the instrument. A generalization claim
requires independently authored semantic migration families and matched model
budgets. Local pilot outcomes must be reported even if the model solves every
case. No intentionally defective control is a model-performance result.

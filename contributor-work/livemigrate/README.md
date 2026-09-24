# LiveMigrate: compatibility during a running migration

**A new evaluation prototype, not an established benchmark or a demonstrated
frontier-model weakness.** This contribution was developed from a fresh audit of
current external work. It does not extend the contributor's older research.

Three coding agents own the database migration, API, and background consumer.
They must jointly implement a data-contract change that works throughout a
running upgrade, while old and new components coexist. A trusted driver supplies
the rollout schedule; the current prototype evaluates their compatible code,
not their ability to choose a deployment plan.

## The failure this measures

An order initially costs $10. A backfill copies that amount to the new schema.
The old API updates it to $15. A new component reads a stale copied amount and
accepts or settles the payment for $10. A later backfill makes the final database
correct. Ordinary final-state checks can pass, but an incorrect externally
visible action has already occurred.

The evaluator records each acknowledged request and settlement independently of
candidate code. A subsequent repair cannot erase an earlier mistake. It also
requires progress and the final new schema, so refusing requests or retaining
the old system forever does not pass.

## What is new, and what is not

Migration, expand/contract, multi-agent SRE, and temporal safety checks all have
substantial prior art. The proposed contribution is the combined executable
contract: **joint API/storage/consumer changes, mixed software versions, delayed
and repeated old events, and exact operation-history grading**.

The [source-level audit](PRIOR-ART-AUDIT.md) compares actual TeamBench and related
graders; the [research note](NOVELTY.md) records alternatives, limitations and
rejection criteria. This is a bounded novelty claim, not proof that no similar
idea exists anywhere.

## Current scope

One genuine migration family: order amounts change from integer cents to integer
micros. Several traffic schedules exercise stale backfill, version coexistence,
revision conflicts, delayed delivery, duplicate delivery and rollback. These
schedules are not advertised as independent task families. Two additional
families are designed in the research note but are not implemented.

- [API contract](API_CONTRACT.md): complete public specification.
- `starter/`: three unfinished role modules.
- `reference/`: conventional correct implementation for evaluator validation.
- `runtime.py`, `scenarios.py`: trusted deterministic SQLite driver and oracle.
- `isolated.py`, `candidate_driver.py`: candidate execution across a process and
  Docker boundary; the expected history is not mounted into candidate containers.
- [Pilot protocol](pilot/PROTOCOL.md): model, calls, visibility, accounting and
  reporting rules fixed before local inference.

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

This one-family demonstrator can validate the instrument. A generalization claim
requires independently authored semantic migration families and matched model
budgets. Local pilot outcomes must be reported even if the model solves every
case. No intentionally defective control is a model-performance result.

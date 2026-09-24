# Research artifact: reusable coordination policy

The outer research loop is distinct from the workers' six-call coding attempt:

1. The research agent forms a coordination hypothesis and edits `scaffold.json`.
2. The evaluator resets each task and runs frozen coding workers under that policy.
3. It independently checks the resulting three modules and reports bounded outcomes.
4. The research agent uses that feedback to revise the policy and submit again.

This is direct evaluation of an inference configuration, not model training.
`pilot/scaffold.py` validates the artifact; `pilot/run.py --scaffold ...` executes
its declared waves. `evaluate.py` fixes the worker profile and two-family workload.
The GPU transport and launch profile are prepared but not hardware-validated.
This is not a completed Harbor task or a measured scaffold-optimization result.

## Exact action space

The JSON has two stages. Each stage calls each of `db`, `api`, and `consumer`
exactly once, organized into one to three ordered waves. Workers in a wave see
the same pre-wave source and messages; later waves receive earlier outputs.
Public checking remains after each stage, with only the first check available
before submission. Instructions consist of a shared string plus one string per
role, totaling at most 5,000 characters. No executable controller is submitted.

The configuration cannot change model, sampling, context/output caps, number of
calls, role ownership, task packet, feedback timing, workloads, oracle, or final
score. A final artifact is one configuration used unchanged across both families.
The intended action space is generic coordination/review guidance. Embedding
task solutions, scenario identifiers, answers or family-specific source code is
outside it. Text validation cannot perfectly enforce that semantic restriction.

`baseline.json` is the simple two-wave pilot scaffold. `contract-first.json` is
a stronger, declared comparison: the database author defines its contract before
API and consumer implementation in each stage. Neither is a claimed best method.
The prepared research reference is `contract-first.json`; its Qwen result is
unmeasured. Local maximum-reasoning Codex successes under the simpler scaffold
must remain visible and are not evidence of a Qwen baseline score.

`protocol-first.json` is an additional strong control prepared for the separate
owner prototype before its model calls. It orders source/storage, API/gateway,
then consumer/owner in each stage, so every later author sees preceding code.
It uses the same six role calls and public-check cadence. This is not a measured
improvement or a change to the frozen earlier pilot results.

## Fixed worker and resource opportunity

Use the pinned current BF16 Qwen profile in `../compute/qwen38.json`, with the
same sampling and seed for reference and candidate policies. Each family gets
six calls. Each call reserves at most 32,768 context tokens and 16,384 generated
tokens inclusive of reasoning. Prompt tokenization must leave that output
reservation intact; no truncation or hidden replacement generations are allowed.
Every generated response, including an invalid response, consumes its call.

The maximum input-plus-output allowance is 196,608 tokens per family and 393,216
across two families. These are matched resource caps and role ownership, not a
claim of equal realized token usage, adaptive depth or latency. Changing wave
dependencies is the experimental intervention. Actual tokens, invalidity and
latency remain reported. Cached input and reasoning subsets are not counted twice.

Each evaluation copies the protected Python, Markdown and JSON sources from
explicit source directories into `OUTPUT/frozen/contributor-work/livemigrate`,
plus the required sibling CLI transport source. Results, caches, nested model
directories and weight files are excluded. The controller compares the original
read hashes before and after copying, verifies the copy before each family, and
checks it again after execution. Every pilot and adapter runs from this copy
using its copied model profile. A changed source or scaffold makes the evaluation
unscored; completed calls and their reported consumption remain recorded.

Budget verification reads exactly `call-00` through `call-05` for each family.
Each must attest one generation, zero retries, complete inclusive token accounting,
the expected worker revision, and matching serving version. Input reservation,
generated-token caps, total arithmetic and token subsets are checked per call.
Missing, extra, partial or inconsistent records make `bounded_usage_verified`
false and the evaluation unscored. All families retain diagnostics, including
those after an invalid first family. `known_input_plus_output` preserves reported
complete input/output pairs; the complete total is null when accounting cannot
be verified. These checks do not attest the server's actual weight bytes.

Once GPU preflight succeeds, from the LiveMigrate root:

```sh
python3 research/evaluate.py --scaffold research/contract-first.json --output /absolute/new/baseline-run
python3 research/evaluate.py --scaffold /absolute/scaffold.json --output /absolute/new/candidate-run
```

The reference need not be rerun for every candidate. Materialize it from the
pinned JSON without training or evaluating during Solution setup. Reproduce it
first under the fixed profile; use repeated runs only if observed variation can
change the conclusion. Seed 0 is not a guarantee of deterministic GPU inference.

## Score and limits

For completed valid generation and evaluation of both families, maximize the
mean of each family's fraction of three history-safe held-out traces. Passing
requires correct client responses, effects, progress and final state. The traces
are correlated; there are two semantic families, not six independent tasks.
Invalid code, inference truncation, infrastructure failure and incomplete checks
remain unscored with diagnostics. No family may be silently excluded.

An eventual Judge returns aggregate and per-family scores, validity and bounded
violation categories. It withholds exact final schedules, oracle state, solution
sources and private reasoning. Public diagnostic traces remain available to
the worker controller. All inputs and methods are publicly reproducible in
this prototype; publication prevents claiming permanently secret held-out data.

The two public references and small search set leave serious hard-coding and
adaptive-overfitting risks. A network-disabled Work packet should omit reference
solutions and final schedules; trusted Judge code checks protected source hashes
and passes only the allowlisted public packet to workers. These are implementation
requirements for the Harbor port, not a claim that a generated port already exists.
Judge evaluates the complete Work snapshot with Judge-only tests; this does not
provide an independent clean Base. The local Docker callback boundary protects
the operation-history oracle from candidate imports, but is not itself an entire
RSI-Harness security boundary. Broader semantic transfer remains unestablished.

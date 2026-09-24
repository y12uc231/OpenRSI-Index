# Reservation ownership migration: research prototype

This draft asks a team to implement three cooperating services that migrate reservation authority while atomic bundles span old and new owners. Four processes have separate durable SQLite stores: a legacy source, a gateway and two new owners. They communicate only through messages. The authors choose private schemas and the internal wire protocol; the external contract and audit projections are public.

This is one migration family with four causal schedules. It is not an exhaustive distributed-system checker, a novel transaction algorithm, or evidence that current models perform poorly. There have been no model runs on this draft at the time of its initial validation. Earlier simpler families saturated and motivated a more substantive interface. Three authors are an experimental arrangement; a centralized agent can implement all files and is an essential control.

## Files and scope

- `API_CONTRACT.md` defines the entire candidate interface and failure model.
- `PUBLIC_SCENARIO.json` is an example traffic schedule, without oracle answers.
- `starter/` contains the three author-owned modules.
- `reference/immutable_v1.py` is the published legacy helper, supplied separately as read-only `legacy.py` inside the sandbox.
- The other `reference/` modules are a constructive solution; they are never given to evaluated authors or mounted with candidates.
- `runtime.py` owns independent capacities, call history, irreversible effects and prefix checks. Its default loader is restricted to trusted reference and test code.
- `scenarios.py` defines one public and three final causal traces. Public repository files are not a secrecy boundary: a scored run must expose only its declared public packet and keep final fixtures out of candidate prompts and containers.
- `history.py` independently checks the observed finite client history using bounded exact search. It does not enumerate network interleavings.

The architecture reuses the invocation contract and external isolation infrastructure developed for the earlier LiveMigrate prototypes. The four-store message runtime, reference protocol and resource/history oracle are new code for this draft. Root contributed the independent history checker; separate reviewers checked its outputs against brute-force history enumeration.

## Trusted CPU validation

From this directory, using Python 3.11 or newer:

```sh
python3 -m unittest discover -s tests -v
python3 runtime.py --candidate reference --suite all
```

Initial results on Python 3.12.14 / SQLite 3.53.1: 27 tests passed, reference 4/4, about 1.0 second for the trusted four-case suite. Individual reference cases use 744–792 callbacks. These timing numbers exclude Docker isolation and model inference; isolated timing is measured separately before a pilot. A callback may use a fresh Python process and only SQLite state is durable.

Generated candidates must run through the core `MultiStoreInvoker` with one database directory per container and only the public helper included. Do not use the direct trusted loader for model output. The isolated oracle requires Python 3.11+ so SQLite value limits are available. Per-query VM and returned-byte bounds are enforced in addition to row limits. This is bounded SQL execution, not a proof of resistance against all adversarial SQLite resource attacks.

## What the controls establish

Positive controls pass all four cases with a different internal message vocabulary and target schema, with draining prepared work before transferring a SKU, and with early acknowledgement after a durable global commit decision. These guard against forcing the reference's representation, transfer recipe or acknowledgement timing.

Three negative controls finish with correct final capacity and completed migration but fail permanently on the live trace:

| Bug | Permanent observation |
| --- | --- |
| Fulfill while preparation is still incomplete | Effect occurs without a valid commit certificate |
| Block every transaction behind a delayed X/Y bundle | Independently available Z misses its published stable window |
| Temporarily activate both source and target, then repair | Two active authorities coexist before final reconciliation |

One negative control releases prepared capacity after an irrevocable global commit; the oracle retains that failure. Another falsely acknowledges an abort without freeing its prepared Y line; a later satisfiable X/Y request reveals the capacity leak and fails both the independent history check and final capacity check. Each scored trace has eight calls, including a partially satisfiable bundle that must abort atomically and a changed-payload retry of an existing committed ID. Regression tests cover global reservation identity across old/new entry points, including an identical legacy retry of a v2 request and a changed cross-SKU retry after handoff.

Infrastructure errors propagate as unscored. Invalid code/protocol has a separate candidate-invalid status. History-search and SQL-budget exhaustion remain unscored; no truncated exploration is reported as exhaustive. Completed executions with semantic violations receive zero.

## Limits before any broader claim

The scenarios do not cover every message schedule, ownership topology or reservation workload. The oracle checks supplied audit projections against public inputs, conservation, history and immutable source tables, but this is not a full proof of truthful arbitrary target representations. Target private representations intentionally remain flexible. Permanent node/storage loss and progress through permanent partitions are outside the contract.

A six-call tool-free feasibility pilot cannot establish performance of full coding agents with normal testing tools. A stronger study needs centralized and protocol-scaffolded team controls, matched inference/test budgets, more independently specified tasks, and held-out transfer tests for any learned coordination policy. If strong current models solve this draft, report saturation rather than adding outcome-driven traps.

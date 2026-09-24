# Local feasibility pilot — frozen before inference

## Purpose

Test whether the task, interface and independent history checker are executable,
and observe actual coding failures or successes. This is not a cross-model
leaderboard or evidence that most models perform poorly.

The task currently asks agents to **write compatible DB/API/consumer code**.
The evaluator controls deployment phases and traffic. Agents do not choose the
rollout schedule. Evaluating autonomous rollout decisions is a possible later
extension, not implemented behavior.

## Fixed model and modes

Use the existing local Codex CLI transport, requesting `gpt-6-astra` with `ultra`
reasoning. The server does not expose an immutable model snapshot ID; record
this limitation. No tools, browser, shell, apps, or repository access are enabled
inside the model call. The adapter receives only explicitly assembled public
text and returns source strings under a JSON schema.

- **Team:** three independent role contexts own `db.py`, `api.py`, and
  `consumer.py`. Each receives the complete same task contract, immutable legacy
  code, and all starter/current peer source. Two rounds of three calls. Calls in
  a round are concurrent; outputs and messages are shared before the next round.
- **Centralized diagnostic:** one context can replace all three files on each
  call, for six sequential calls. Full current source and previous messages are
  supplied each time.

Both receive one public check after the first three calls and another after
the last three. Only the first check can affect the submitted artifact. The
candidate hashes are frozen before evaluating withheld stress traces. No retries
or replacement generations after a valid model response. Provider/infrastructure
failure makes the run incomplete, not a zero-success model result.

Six calls per mode is **not a matched token or adaptive-depth budget**. The team
has two revision opportunities, while the central mode has six. Central outputs
also have a larger schema. These two arms can diagnose feasibility; their score
difference cannot establish a causal teamwork advantage or disadvantage. Record
all reported input, cached-input, output tokens and elapsed times. A later
controlled study must match the relevant inference and tool budgets explicitly.

## Frozen workload

One order-service migration family, the complete `public` suite and complete
`heldout` suite from `scenarios.py`. Freeze all code, contract, schedules, starter,
reference and driver hashes before any inference. Schedules are correlated
stress cases, not independent software tasks. The word "heldout" means withheld
from pilot prompts; once published, they are public reproducibility cases, not
a permanently secret generalization set.

Run reference and bug controls first. Reference must pass every trace. The
checker must reject at least one deliberately incorrect implementation that
passes final-state checks. Freeze this protocol and the executable version in
Git before launching model calls. Do not drop or replace cases after outcomes.

## Execution and isolation

Use the already present public Python image:

`python@sha256:23b5dc88c7dd47fec3f960b51dc30d19df9875cfbfc60f3b62d3e5b88cbccf62`

The preferred `isolated.py` dispatcher executes submitted callbacks in a
network-disabled Docker container. The expected operation ledger and settlement
oracle remain in the host evaluator, outside the candidate process and mounts.
The direct `runtime.py` loader is for trusted reference and unit tests only.

Candidate syntax/exception failures are reported as candidate-invalid with no
aggregate model score. Complete, executable implementations with incorrect
semantics receive failed case outcomes. Infrastructure failures/timeouts remain
unscored. Malformed or incomplete runs must not be silently converted to model
failures. A callback timeout needs attribution review before classification.

Each inference call has a 480-second operational timeout; each suite check has
a 180-second timeout. These protect local execution, not benchmark difficulty.
This pilot uses CPU environment execution and local Codex inference. No GPU is
required to execute its database workload.

## Commands

From this directory's parent:

```sh
python3 pilot/run.py --mode team --output /absolute/new/run-directory
python3 pilot/run.py --mode centralized --output /absolute/new/control-directory
```

For another model, supply `--adapter-command` followed by a command that accepts
one JSON object on stdin with `prompt` and `schema`, and returns exactly the
schema-conforming response object on stdout. This is a transport interface,
not a claim that any other provider has been evaluated. Credentials remain
outside the repository and are managed by the adapter.

## Reporting

Before the first inference in this family, a second semantic family was selected
for implementation: global-to-tenant request identity, as specified in
`REQUEST-ID-BLUEPRINT.md`. Its selection does not depend on this pilot's outcome.
Its implementation and cases must be separately frozen and validated before
its own model calls. Report the complete result of each declared family; no
after-the-fact family exclusion based on score.

Report complete pass, static/final-state pass, history pass, and migration
completion separately, with exact numerators and denominators. Also report
invalid/incomplete counts. Publish the source revision, artifact hashes,
summary metrics, and replayable counterexamples. Keep raw inference events,
reasoning, local paths and authentication metadata outside public artifacts.

If all models pass, report that result. Do not present negative controls as model
outputs or published scores from other benchmarks as measurements of this task.

# Public-check allocation policies

These policies schedule real workers and public integration checks; they do not solve repository features, read hidden tests, or contain task-specific answers. Their performance is unmeasured until the real runner executes them. The adaptive policy is a candidate hypothesis, not an asserted improvement.

## Fixed controls and candidate

| Configuration | Public-check allocation |
| --- | --- |
| `configs/periodic.json` | Reasonable baseline: share latest teammate messages and check a dirty integrated candidate every two worker calls. |
| `configs/always_verify.json` | Check each changed candidate, subject to the same check cap. |
| `configs/adaptive.json` | Check a dirty candidate when worker edits overlap in a file or syntactic exports/imports indicate a cross-worker dependency; otherwise use a four-call periodic fallback. |

All policies use identical balanced worker scheduling, teammate messages, public failure feedback, a changed-candidate repair recheck, and an affordable final public-check barrier. After a failing check, a worker gets a repair turn before unchanged code can be checked again. The runner decides when a worker is done and increments the relevant counters. File overlap and patch-derived symbol relationships are fallible heuristics, not evidence that integration is correct or incorrect. The initial runner uses regular expressions over added diff lines, not complete AST or dependency analysis; it can miss removed definitions and preexisting imports. A successful old check never certifies a changed candidate hash.

The independent final Judge **always** runs its protected feature tests after `finish`, even if the worker or public-check budget is exhausted. Public `joint_verify` actions use only baseline tests and candidate-written tests exposed to workers. Hidden feature tests, grader feedback, and gold patches must never enter policy state or worker prompts. Public-check exhaustion does not make the final submission unscored.

## Callback contract

```python
from policies import Policy
decision = Policy(config).action(state)
```

`state` is a JSON-serializable dictionary:

```json
{
  "workers": [
    {"id":"worker_1","turns":2,"done":false,"revision":"patch-hash-1",
     "changed_paths":["api.py"],"exports":["parse"],"imports":[],"message":"Evidence or status"},
    {"id":"worker_2","turns":1,"done":false,"revision":"patch-hash-2",
     "changed_paths":["client.py"],"exports":[],"imports":["parse"],"message":"Evidence or status"}
  ],
  "candidate_hash":"hash-of-current-integrated-code-or-patch-pair",
  "verified_hash":"hash-to-which-last-public-result-applies",
  "last_verify_passed":true,
  "turns_since_verify":1,
  "last_worker_id":"worker_1",
  "verification_feedback":"actual public test output, if available",
  "worker_calls_remaining":17,
  "checks_remaining":3
}
```

Required counters are nonnegative integers. `candidate_hash` is null until a candidate exists; `verified_hash` is null until public verification. It must fingerprint every relevant worker revision and integration state, including a failed merge, so changing either worker invalidates the old check. `last_verify_passed` is null before any check. Worker revision/footprint values come from observed artifacts, not unverified model completion claims. Footprints should correspond to actual branch diffs relative to the common baseline; document parser limitations consistently across controls.

The result is `{action, worker_id, integrate, message_context, reason}`. `action` is `worker`, `joint_verify`, or `finish`. A verification decision sets `integrate=true`; the runner merges and runs its public tests. A worker decision identifies the next worker and supplies latest teammate messages and public test feedback as a list of strings. A `finish` decision never substitutes for the final Judge. The callback does not mutate the supplied state or maintain hidden state between calls.

## Budget ledger

```python
from policies import BudgetLedger
ledger = BudgetLedger(max_calls=32, max_checks=4)
ticket = ledger.reserve_call()  # count-limited local Codex mode
# Run exactly one model call with the runner's fixed wall-clock timeout.
ledger.settle_call(ticket, reported_usage)
check = ledger.start_tool(is_check=True)
# Integrate and execute PUBLIC tests.
ledger.finish_tool(check, measured_seconds)
report = ledger.summary()
```

The current local CLI lane has no verified enforceable per-call output-token ceiling. Its 32 model-call and four public-check caps are exact scheduling caps; total reported tokens are diagnostic, **not a matched token budget**. The runner must pass these limits explicitly (the generic ledger's constructor default is not an experiment specification). Every model invocation—including any future model coordinator—must reserve a call. Fixed per-call wall-clock limits are enforced by the runner, not inferred from token counts. Reservations count attempts, including failed attempts; no silent retry or refund is supplied by this ledger.

For a later endpoint with enforceable caps, configure `max_total_tokens` and call `reserve_call(input_upper_bound=..., output_token_limit=...)` before launch. Illustrative 32K input / 4K output bounds are not a selected experiment budget. The input bound must include all actual system/tool/history tokens, and the provider output ceiling must include reasoning tokens. Concurrent reservations cannot exceed the remaining token pool. Actual usage exceeding either bound marks an overrun and blocks further reservations; it is never presented as compliant.

Normalized usage accepts `input_tokens` / `prompt_tokens` and `output_tokens` / `completion_tokens`, requiring equal aliases if both appear. Input and output totals are inclusive; cached input tokens and reasoning tokens are tracked as subsets and never added a second time. A supplied `total_tokens` must equal input plus output. Providers with different cache accounting must normalize explicitly. Missing, contradictory, nonintegral, or otherwise malformed telemetry raises `TelemetryError`; aggregate tokens become null rather than zero. A token-budget lane must stop or remain unscored for budget compliance. A call-count pilot can still report its Judge outcome while clearly marking token comparison unavailable.

Use `start_tool()` / `finish_tool()` for ordinary tools as well as public checks. Total tool seconds are the sum of observed tool durations, not process CPU time or end-to-end elapsed wall time. Optional tool-time ceilings are metered and can stop further work, but require runner-enforced remaining-time limits for a hard guarantee. The mandatory Judge's independent evaluation cost should be reported separately from optimization tools and public-check allocation.

Run the offline invariants/accounting tests from `contributor-work/jointverify` with `python3 -m unittest discover -s tests -v`. These tests produce no model scores and invoke no external service.

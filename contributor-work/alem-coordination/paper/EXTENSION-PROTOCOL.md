# Sol continuation study — declared before the new model calls

Date: 24 September 2026. Status: planned independent-paper experiment.
OpenRSI submission is on hold. This study does not change or replace the original
three-call Astra/Sol pilot. No claim of a publishable new method is assumed.

## Question

Does six more rounds of controller development improve the best available
controller, and does the selected controller work on worlds that this new
research loop has never evaluated? What changes when its explicit JSON memory
is reset or its added communication actions are suppressed?

This is a continuation from a selected successful pilot, not an independent
sample of researcher ability or a fair comparison against the three-call Astra
run. Sol's old evaluation score helped motivate its selection. The old 20 worlds
are therefore a regression set, not a clean final test for this continuation.

## Fixed starting point and budget

- Use the requested local model alias `gpt-6-sol`, with `ultra` reasoning, through
  the same tool-free Codex CLI transport. No immutable server version is exposed.
- Make exactly six new coding calls if execution completes. A malformed response,
  model-access failure or infrastructure error stops the study; do not silently
  retry or replace it. Validly recorded invalid controller trials can receive
  diagnostic feedback and consume one of the six calls.
  Controller source larger than 1 MiB is a recorded invalid submission. It is
  not executed, receives that size diagnostic, and consumes its call.
- Start the code context from the original final Sol controller, SHA-256
  `3862d57dbf57dbb8e1f2efff6cd32a345dd7006a0dab58d40b45e0ff5ae38d89`.
  Its old development reward was 19.8113%; the pass-through reference was better
  on development, at 22.4843%.
- Use the original public source packet. Add the current single-container
  filesystem limits and this continuation's budget/selection instructions.
  Do not send original per-world evaluation results or fresh-world results.
- After each call, evaluate its code on all four development worlds,
  20000–20003. Return only the existing allowlisted aggregate feedback.
  The next call receives the latest controller, the best controller so far,
  and the development history. No manual code fixes or extra method suggestions
  are inserted between calls.
- Keep every response, controller, outcome, model-usage record and elapsed time.
  Raw prompts, reasoning, notes and private paths stay outside the public repo.
  Count cached input and reasoning output as subsets, not extra tokens.

## Selection rule, fixed before results

First rerun pass-through and the original Sol controller on the development
worlds using the current audited runtime. Require agreement with their original
per-world game histories before new inference. This checks deployment; it does
not add researcher samples.

Eligible candidates, in tie-breaking order: pass-through, original Sol, then
new calls 1–6. Choose the valid controller with the highest mean development
coordination reward. An exact tie keeps the earliest candidate. Invalid or
incomplete outcomes are retained but cannot win. Including pass-through avoids
forcing a controller that is already worse on development.

Freeze the selected source and checksum after call six and before any final
comparison. Do not choose a different controller after seeing final results.

## Final comparisons

Run pass-through, original Sol and the selected controller on:

1. The original public regression worlds, 9999–10018.
2. Twenty new transfer worlds, 30000–30019, in increasing order.

The new range is fixed now, before generating or evaluating these worlds in
this study. It is one contiguous range from the same procedural generator, not
a secret test set, a random sample of every possible map, or proof of an unseen
training distribution. Do not regenerate these worlds during development.
If two submitted files are identical, reuse that exact result and label the
reuse; do not count it as an independent evaluation.

Primary endpoint: selected controller's mean coordination reward minus
pass-through on the new 20-world set. Also report the change from original Sol,
all three raw scores, and every world's paired difference. Original-world
changes are secondary regression results. Deaths and valid zero rewards remain
included. A score requires all 20 valid outcomes. Invalid code, timeout and
infrastructure failure remain unscored, with their records kept.

The game, checkpoint, configuration, observations, masks, action rights, reward,
10,000-step ceiling and per-world random-number formula stay unchanged. Only
staged copies of the suite declarations change to admit `transfer`. Record that
patch, all runtime hashes and the exact world list. Do not modify the original
controller, native evaluator or pilot source.

## Two predeclared diagnostic interventions

If the selected file is pass-through, report that result and do not manufacture
an ablation claim. Otherwise run these two variants on both final suites after
selection. Neither result returns to the researcher.
If a valid selected controller cannot be wrapped (for example, its names clash
with the wrapper's reserved names), keep the main final comparisons and mark
that intervention unavailable. Do not change the selected controller to make
the intervention work.

- **Reset explicit JSON memory:** call the original initializer once per actor
  and world. Save its JSON value. Before each action, supply a fresh copy of that
  value instead of the previous returned memory. Keep normal output validation.
  Module globals and private files remain available. This tests the declared
  JSON-memory channel, not all possible memory.
- **Suppress controller-added messages:** if the controller chooses a native
  communication action different from the trained model's suggestion, execute
  the suggestion instead. Keep the controller's returned memory. Native messages
  already proposed by the trained model remain allowed. Record actual
  suppression markers from complete private actor logs, or mark that diagnostic
  unknown if logs are incomplete. These markers are implementation diagnostics,
  not a security proof against deliberately forged candidate output.

These are interventions on the complete controller's behavior. They do not
isolate a pure effect of communication or memory: substituted actions can change
survival, and retained memory can describe a message that was not sent. Report
survival, synchronization attempts/successes, handovers, construction, action
changes and communication counts alongside reward. Zero actual intervention
means there is no mechanism evidence from that variant. A no-trained-policy
comparison remains necessary before claiming that the learned policy is useful
or that the method is better than writing a controller from scratch.

## Execution and limits

Use one ordinary network-disabled Linux arm64 container per evaluation, four
CPUs, 16 GiB RAM, at most 256 processes and zero GPUs. Use the already validated
image `sha256:9282bdeb7b8debc675830cf464028cba51b9a7b83afd8c1f4c098f67edd73176`.
Keep source/assets/candidate read-only and use the existing private-process
restrictions. Never import generated controller source on the host.

Each model call has a 1,800-second operational ceiling. Each evaluation has
10,800 seconds plus bounded shutdown time; each actor reply has 30 seconds.
Serialize evaluations through the existing lock. No automatic retries. Record
source, candidate, packet and protocol hashes before and after the study.

Six adaptive rounds on four development worlds can overfit. A selected warm
start, one model alias, one trained checkpoint, one research trajectory and
forty final worlds cannot establish broad model rankings or a general new
algorithm. A paper needs a clear difference from the closest published methods,
stronger comparisons and reproducible findings. Publication is a decision after
this evidence is reviewed, not the assumed outcome of the experiment.

# Review of the proposed six-call Sol follow-up

This is a study-design review, not a report of new results. No model or benchmark
was run for this review. The existing pilot and its published scores must remain
unchanged. A separate paper protocol should be fixed before the first new call;
this note does not itself certify that a protocol has been registered or run.

## A useful question for this small study

Can six more code revisions improve a fixed RL team's coordination on new game
worlds, and does the selected controller depend on its explicit memory or its
added communication actions?

This can produce a careful case study. More reward from one continued attempt
would not by itself establish a new research method, reliable model superiority,
or a general solution to multi-agent coordination. The game actors remain
frozen RL policies with local Python controllers, not an LLM conversation team.

## Selection: allow the baseline to win

The original Sol final controller scored **19.8113%** on the four development
worlds, below pass-through's **22.4843%**. On the original twenty evaluation
worlds it scored **19.4654%**, above pass-through's **18.5220%**. This reversal is
already evidence that a four-world ranking need not transfer. These figures are
reward percentages, not pass rates. See the [complete pilot results](../results/README.md).

Use the original Sol final source as the starting code, but make pass-through
an eligible selection candidate. Rank candidates using the complete, unrounded
four-world development mean, with this fixed order for exact ties:

1. Pass-through.
2. Original Sol final controller.
3. New submissions 1 through 6, in order.

Select the highest-scoring valid candidate. A candidate is eligible only after
all four declared worlds finish with valid scores and verified source/runtime
records. An invalid or incomplete result is unscored, never zero. Preserve it
and its known cost. The same rule must apply to the starting candidates; use
measurements from the declared matched runtime, not a mixture of configurations.

Publish all six submissions and their development outcomes, including duplicate
code, regressions and failures. Do not replace failed model responses, silently
extend the call budget, or select using an evaluation result. Declare separately
what happens if a provider or infrastructure interruption prevents six calls;
an incomplete attempt must not be presented as a completed six-call study.

Freeze what each next prompt receives. A simple choice is the best eligible
code so far, the preceding submission's code, and the complete table of prior
four-world aggregate scores and bounded validity diagnostics. The first prompt
must still include the original Sol controller and its development result.
If the intended runner instead supplies only the latest code, record that rule
before starting and keep it fixed. Avoid undocumented manual hints between
calls. Match the prior aggregate-feedback schema unless a deliberate feedback
change is part of the new protocol.

## Separate development, regression and new-world evaluation

| Set | Purpose | Exposure and use |
| --- | --- | --- |
| Development: 20000–20003 | Improve and select code | Return only the declared four-world aggregate feedback during all six calls. It is training feedback, not a holdout estimate. |
| Original evaluation: 9999–10018 | Check behavior on the established workload | Its results are public and informed the decision to continue Sol. Call it the original or regression set, not a clean independent holdout. |
| Fresh twenty worlds | Test the selected code on previously unevaluated worlds | Fix the full list and selection procedure before any new model call. Reveal outcomes only after the winner and analysis plan are frozen. |

For a paper about generalization, the fresh set should be part of the declared
study, not an option chosen after seeing results. If it is omitted, report only
the fixed-workload case study. Fresh worlds from the same generator test new
worlds under the same setting; they do not establish transfer to new games,
difficulties, checkpoints or teammate policies.

Choose fresh seeds without inspecting generated maps or baseline difficulty.
For example, preregister a fixed public hash-based sampling rule over the legal
seed space, exclude all previously used seeds, and take the first twenty unique
values. Record the resulting list, source/checkpoint pins, Hard configuration,
10,000-step horizon and existing per-world RNG rule in a manifest. Do not drop
uninteresting, difficult or failed worlds. This is a recommendation for the
protocol owner to instantiate, not a selected seed list.

Evaluate the selected code and pass-through on every fresh world using identical
world and transition seeds. Also evaluate the unchanged original Sol incumbent
on that set as a fixed secondary comparison: otherwise an apparent improvement
may merely preserve the starting artifact's behavior. This comparison must not
change which candidate wins. Re-running a baseline is a matched deployment
check; changing its configuration is a new baseline and must be labeled.

The old code and outcomes are public, and the researcher is deliberately
warm-started from a previously selected artifact. Disclose that exposure. A
fresh set can protect this study from using its own evaluation feedback, but
cannot prove the model has never encountered related public material. Do not
add original per-world evaluation results or any new evaluation/ablation results
to continuation prompts. Record historical aggregates already included in the
research packet; removing them now does not undo earlier exposure.

Returning only averages does not prevent overfitting: repeated feedback can
adapt the program to those same four worlds. This is the concern addressed by
[The Ladder](https://proceedings.mlr.press/v37/blum15.html) and
[Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.neurips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html).
The proposed study does not implement their formal protections and should not
claim their guarantees.

## Two fixed interventions to test controller features

Freeze and hash the wrappers before the first new call. Apply them only after
selection, using the unchanged selected source. Run them on all original twenty
and all fresh twenty worlds. Never return their outcomes to the researcher.
The wrappers are experimental interventions, not repairs of a controller.

| Variant | Exact behavior | What its comparison can show |
| --- | --- | --- |
| Unchanged selected controller | Run the submitted code normally. | The selected program's total effect relative to pass-through. |
| `reset_explicit_json_memory` | Initialize once per actor/world and save a deep copy of the initial JSON memory. Before every `act`, provide a fresh copy of that initial value. Validate the returned memory normally, then discard it. Keep module globals, files, local observations and the trusted recurrent policy unchanged. | Dependence on carrying the explicit JSON state between steps. It does not remove all memory. |
| `suppress_controller_added_comm` | Validate the controller result normally. If its chosen action is a native communication action and differs from the frozen proposal, execute the frozen proposal instead. Keep the controller's returned memory. Preserve communication already proposed by the frozen policy. | The total effect of allowing the controller's added communication actions under this replacement rule. It does not remove all communication. |

Do not call `initialize` again on every step: it could mutate module globals,
so that would test something beyond resetting explicit JSON memory. All actors
still start with fresh processes per world. The trusted recurrent policy must
continue to advance on actual observations, and the original legality, memory,
timeout and provenance checks must remain active. Never import generated code
on the host to implement these wrappers.

Static reading of the original Sol source makes these interventions relevant.
Its explicit memory records focus, age, cooldowns, pending handovers and recent
starts. Its action logic sends native messages while waiting for a readiness
quorum. See the [unchanged final source](../results/sol-001/generation-03/controller.py).
A future selected revision may use these features differently, so count actual
interventions instead of assuming that the wrapper has an effect.

Record memory resets, suppressed actions, final communication actions,
overrides, survival, synchronization attempts/successes and all native reward
components. If no added message is suppressed, that ablation supplies no
information about the value of communication. Keep wrapper-invalid outcomes
unscored; an invalid wrapper run is not a zero-reward causal result.

If suppression counts come from a fixed marker in private agent logs, count
only complete, untruncated logs. Otherwise report the count as unknown. Exclude
the marker from the original candidate source. The candidate shares an
interpreter with its wrapper and could still spoof output, so these counts are
diagnostics, not a security proof. The trusted engine's reward remains the
primary measure.

These are narrow causal interventions on a fixed program. Removing remembered
cooldowns may alter navigation and survival. Suppressing an intended message
while retaining the program's memory can leave its bookkeeping inconsistent
with what happened; replacing the message with another action also changes the
world. Therefore the reward difference includes those downstream effects. It
is not a pure estimate of communication efficiency or a proof that memory and
communication independently explain the gain.

The original controller already changed survival as well as synchronization:
mean alive-agent steps rose from 1,064.05 to 1,117.25, while mean episode
synchronization success rate fell from 0.5695 to 0.4621. Report both reward and
opportunity-related counts. Do not condition only on surviving episodes or
present successes per alive-agent step as a causal adjustment: survival itself
can be changed by the controller.

A fourth variant applying both wrappers would permit a two-by-two interaction
comparison. It is optional for this small study, but must be declared before
calls if used. Without it, report two separate total-effect interventions and
make no claim that their contributions add up. If pass-through wins selection,
retain that outcome; the planned winner ablations then offer no nontrivial
controller-mechanism evidence. Do not replace the winner to force a positive
paper narrative.

## Primary result, uncertainty and replication

Make the primary endpoint the selected controller's mean coordination-reward
difference from pass-through on the fresh twenty worlds. Keep the original
set's difference, comparison with the old Sol controller, and both ablation
contrasts secondary. Report percentages and percentage-point differences,
every world, win/tie/loss counts, and all invalid/incomplete outcomes.

Use paired differences: compare variants on the same world. A preregistered
paired bootstrap over the twenty fresh worlds can give an approximate interval
for the mean difference, conditional on the selected controller and the seed
sampling procedure. Fix its resample count and analysis seed in advance. Do
not treat three agents, thousands of steps, or repeated deterministic replays
as independent research attempts. For the fixed original worlds, descriptive
variation is sufficient; do not call it fresh generalization uncertainty.

Twenty worlds remain a small sample. Show the points and sensitivity to the
largest gains/losses; do not quietly change the primary mean to another metric
when results disappoint. Label the two mechanism contrasts exploratory unless
a multiple-comparison rule was declared. If making confirmatory significance
claims for both, preregister a correction such as Holm's procedure. The relevant
RL evaluation warning is uncertainty from limited independent runs, not merely
missing error bars: see
[Deep Reinforcement Learning at the Edge of the Statistical Precipice](https://arxiv.org/abs/2108.13264).

The six calls form one dependent optimization history starting from an already
successful public artifact. They do not estimate variation across independent
researchers, justify a model ranking, or establish an advantage of iteration
itself. Repeated execution of the same deterministic controller tests
reproducibility, not researcher reliability. Provider aliases also do not pin
immutable model versions. Report every accepted response's tokens and time,
including the prior work needed to obtain the starting controller separately
from the six-call continuation cost.

For a stronger later study, predeclare several independent continuation runs
from the same incumbent, plus equal-budget runs from pass-through. To claim
that feedback-driven iteration helps, also compare with the same number of
independent proposals without intermediate feedback, selected by the same
development rule. Three runs per condition would still be a small pilot, not a
universal adequacy threshold. Do not add these comparisons selectively after
seeing a favorable continuation.

## Novelty: what a paper would need to add

| Primary source | Established overlap | Implication here |
| --- | --- | --- |
| [FunSearch, Nature](https://www.nature.com/articles/s41586-023-06924-6) | Language models generate programs that an evaluator scores; program search improves candidates. | The generate–evaluate–revise loop is not new. |
| [AlphaEvolve](https://arxiv.org/abs/2506.13131) | An evolutionary coding agent iteratively improves algorithms using evaluator feedback. | More revisions and a new environment alone do not establish a new discovery method. |
| [Automated Design of Agentic Systems](https://arxiv.org/abs/2408.08435) | A meta-agent writes agent systems as code and evaluates designs, including transfer across domains and models. | Code-written agent control and transfer testing are already research topics. |
| [Beyond Scalar Rewards, v3](https://arxiv.org/abs/2603.19453v3) | Code policies for multi-agent environments are refined through self-play; sparse reward feedback is compared with reward plus social metrics in Gathering and Cleanup. | This directly overlaps LLM-written coordination policies and feedback-driven revision. Calling this the first such study would be wrong. |
| [Discovering Cooperative Pipelines](https://arxiv.org/abs/2605.30003) | An outer coding researcher changes the prompts, feedback functions, helper libraries and iteration logic of a multi-agent policy-synthesis pipeline. | Even an outer researcher optimizing the inner research loop is already studied. |
| [GenSwarm](https://www.nature.com/articles/s44182-025-00065-w) | Language models generate and refine executable multi-robot policy code, including distributed tasks using local sensing. | Local observations alone do not distinguish this study from all earlier policy-code work. |

Gallego's paper was submitted on 19 March 2026 and revised on 30 June 2026; the
record identifies it as an ICML NExT-Game 2026 workshop paper. Its reported
feedback comparison is not evidence for a novel feedback method here. This
follow-up currently changes neither the feedback method nor the evolutionary
search algorithm.

The separate related-work review checked the GenSwarm source, published on
9 January 2026. Some of its tasks allow centralized assignment, while others
are fully distributed; do not dismiss the entire method as centralized.

The defensible prospective contribution is narrower: an auditable study of
local controllers around a fixed recurrent RL team, retaining the policy's real
observations and action rights, with explicit memory/message interventions and
new-world evaluation. Whether that is enough for a standalone paper depends on
the findings, careful comparison with close work, and replication. Neither the
current pilot nor six more calls guarantees a novel mechanism or publishable
result. A clear null result or failure to generalize is preferable to changing
the selection rule, filtering worlds or relabeling exposed data as held out.

The unrestricted interface also permits ignoring the frozen policy. Actual
reliance on it, transfer across checkpoints, and a reusable coordination rule
would need their own comparisons; they cannot be inferred from the wrapper's
name or from this one-checkpoint study.

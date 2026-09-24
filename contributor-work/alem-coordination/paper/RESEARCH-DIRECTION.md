# Decision memo: what would justify an independent paper?

**Recommendation: pursue a small, separately declared transfer study before
deciding to write a method paper.** The running six-call Sol extension is useful
exploration. It should finish under its existing protocol; this memo changes
neither that study nor the frozen pilot. No new experiments are reported here.

The possible contribution is a finding about **helping a trained team coordinate
without taking over the skills it already has**. It is not the general idea of
asking an LLM to write code, measuring reward, and asking for a revision.

## What is already established

[Beyond Scalar Rewards](https://arxiv.org/abs/2603.19453v3) already refines
multi-agent Python policies using game feedback, and
[Discovering Cooperative Pipelines](https://arxiv.org/abs/2605.30003v1) adds an
outer researcher that improves the synthesis process. Their full-state policy
interfaces differ from ours, but
[GenSwarm](https://www.nature.com/articles/s44182-025-00065-w) also includes
distributed code control using local sensing. Local execution is therefore
not sufficient novelty.

[MATES](https://arxiv.org/abs/2609.26010v1) adapts observations for frozen solo
policies, while [MAAF](https://www.mdpi.com/2076-3417/14/21/10079) separates base
behavior from a message-conditioned action adapter. Keeping learned skills
while adding coordination is also an existing research direction. Our possible
distinction is an executable local controller found by code search, with fixed
network weights and no runtime access to the simulator. The
[related-work review](RELATED-WORK.md) explains the overlaps and limits; this
combination is not a guarantee of novelty.

Nor is “reward is not cooperation” itself a new finding.
[Mao and Perrault, 2 August 2026](https://arxiv.org/abs/2608.01425v1), generate
symbolic options and train small LLM option selectors; their behavioral audit
shows that higher reward can accompany one actor doing the work alone. A
[5 July 2026 training-time reward-shaping study](https://arxiv.org/abs/2607.04470v1)
also examines when augmentation helps or harms an already competent baseline.
Those training methods differ from our fixed-weight controller setting, but
their questions must not be presented as new here.

## One concrete question

**Can feedback-driven code search discover a local coordination rule that
improves previously untuned trained teams on new worlds, while still benefiting
from those teams' learned action choices?**

A useful rule might decide when an actor should follow its trained proposal,
commit to a visible joint task, wait for a teammate, or abandon a stalled
attempt. Those decisions can use the existing local observation, masked logits,
native messages and private memory. They need no pooled observations, free
messages, simulator queries, new actions or gradient updates. A commitment
state machine is an obvious solution to try, not a new invention by itself.

The primary prospective claim is deliberately falsifiable: controllers selected
on one checkpoint's development worlds improve mean coordination reward on two
previously untuned compatible checkpoints and new worlds, and feedback-driven
search improves over equally budgeted proposals without intermediate feedback.
Evidence of dependence on the learned policy is a further requirement for the
claim that this *supports* trained competence. Passing only one of these tests
requires a narrower conclusion.

We should initially test the existing unrestricted interface. It lets a strong
controller choose any legal action, including replacing every trained proposal.
Do not impose an override quota or remove a good replacement solution to make
the augmentation story succeed. If a small, transferable intervention emerges,
extract and test it as a subsequent hypothesis before calling it a new method.

## A minimum useful study

This is a proposed next study, not a claim that these comparisons have started.
Freeze its selection rules, budgets and new evaluation set before any calls.

| Component | Concrete plan |
| --- | --- |
| Independent searches | Three fresh research trajectories with feedback and three without intermediate feedback, using the same model/settings and six candidate calls per trajectory: 36 calls in total. Start every trajectory from the same public task packet and pass-through code. The ongoing warm-started continuation remains a separate study. Three runs per condition are a small first study, not a universal adequacy threshold. |
| Fair search control | In the no-feedback condition, generate six proposals in separate fresh contexts from that same packet. Evaluate all six on exactly the same development worlds and select with the same rule as the feedback condition; do not reveal intermediate outcomes to the proposer. Match call limits, total token allowances, evaluator queries and resource ceilings. Report actual input/output usage, failures and wall time, rather than calling unequal costs equal. |
| Selection | Use the existing four development worlds on the designated development checkpoint. Pass-through is eligible and wins exact ties. Keep invalid attempts and their costs; select only complete valid evaluations. Do not force a new controller to win. |
| Transfer | Choose two additional released, interface-compatible checkpoints by metadata and a fixed rule, before inspecting rewards. Freeze one new list of twenty worlds not used for search or previous evaluation. Run each selected source unchanged on the development checkpoint and both untuned checkpoints, with each checkpoint's own pass-through baseline. No per-checkpoint code repair or tuning. |
| Obvious solution | Include one fixed, simple local readiness/commitment controller chosen before outcomes. An automatically generated rule should be compared with this straightforward alternative, not only with doing nothing. |
| Main outcome | Report paired coordination-reward differences on the two untuned checkpoints and new worlds, separately by checkpoint as well as their equal-weight mean. Compare feedback with no-feedback search across independent trajectories. Keep all selected trajectories, including ones where pass-through wins. |

This uses already trained policies and CPU evaluation; it does not require a
training run or a new environment. With six selected artifacts, pass-through
and one scripted control, the main comparison needs at most 24 twenty-world
evaluations across three checkpoints, plus 36 four-world development checks.
Identical source/checkpoint/suite combinations can share one recorded
deterministic evaluation; duplicated measurements are not independent evidence.
Reserve additional evaluations for the small diagnostic study below.

The release metadata make this feasible to investigate: the pinned repository
contains Hard HyperMARL recurrent checkpoints for training seeds 0–4. Configs
for seeds 1 and 2 match seed 0 on the checked observation/action settings and
network architecture fields. They are natural prospective choices by seed
order, before looking at their rewards. This is a metadata check, not a loading
or rollout test. No additional weights were downloaded and no reward summaries
were inspected. The exact configuration URLs and hashes are in
[CHECKPOINT-AVAILABILITY.json](CHECKPOINT-AVAILABILITY.json).

Use measured costs to set a budget before launching. Better survival can make
evaluations much longer than the current reference, so the short reference run
is not a worst-case runtime estimate. If the design is unaffordable, reduce its
scope openly before observing outcomes; do not retain only favorable searches
or checkpoints afterward.

Three researcher trajectories and twenty worlds leave substantial uncertainty.
Show every trajectory and paired world-level result. World variation and
researcher variation are different sources of uncertainty; thousands of game
steps are not thousands of independent experiments. Wide intervals or mixed
checkpoint effects call for replication or a narrower claim.

## Does it support the base policy, and why does reward change?

Before seeing transfer results, choose one diagnostic controller using only the
declared development ranking. These tests explain that artifact; they do not
establish the mechanism of every independent search.

First, record how often it follows and overrides the trained action. Then use
both a declared fixed-code input intervention and a competitive controller-only
search with a matched budget. Removing logits or replacing a proposal can
break assumptions in existing code, so a failing ablation alone does not prove
that the trained policy is useful. Conversely, a similarly strong controller
that never receives learned outputs would weaken the augmentation claim. It
could still be a useful standalone policy-code result, with closer prior art.

Second, retain the already declared memory and added-message interventions as
narrow diagnostics where applicable. A native message consumes a turn.
Suppressing it changes the action, timing, subsequent observations and possibly
survival. Keeping its intended message in private memory may also make the
controller's bookkeeping inconsistent. Reward differences therefore measure
the total effect of that intervention, not the isolated informational value
of communication. Count actual interventions and report survival, joint-task
attempts/successes, base reward and communication use alongside reward. Do not
condition only on survivors or treat success per surviving step as a causal
correction. A pure communication-content claim would need a separate experiment.

The first-stage transfer study can motivate these comparisons. A matched
controller-only search with three six-call trajectories would add 18 candidate
calls, 18 development checks and nine twenty-world transfer evaluations. Those
costs are additional to the first-stage budget. A full claim about dependence
on learned competence needs that comparison; a small fixed-code ablation is
not a substitute for a strong replacement baseline.

## What would make us stop or change the claim?

- Gains disappear on both untuned checkpoints or new worlds: we have workload
  specialization, not a transferable coordination rule.
- Feedback performs no better than matched independent proposals: there is no
  evidence for the value of this feedback-driven search procedure. A useful
  found controller may remain, but not the proposed search advantage.
- Pass-through or the simple scripted controller usually wins: the generated
  method has not earned its additional research cost.
- A competent controller-only alternative matches the gain: describe policy
  replacement unless other evidence establishes a benefit from the learned
  base. Do not redefine that result as augmentation.
- Reward rises while proposed coordination mechanisms do not survive controlled
  tests: report the actual effect, which may be survival or resource management,
  rather than invent a communication explanation.
- Results depend on one search, one checkpoint, an invalid evaluation or a few
  unusually favorable worlds: preserve those outcomes and withhold a broad
  reliability claim.

A reproducible null result can still be informative. A strong independent
paper needs a useful general finding or a clearly specified method with
convincing comparisons. The current packaging, one promising controller, and
more iterations are a starting point for that work, not evidence that the
paper contribution already exists.

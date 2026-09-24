# Alem Coordination Lab: research task design

Status: implementation and feasibility study, not an accepted OpenRSI task or a
claim that contemporary research agents fail. This document is not the formal
proposal. The final proposal must use OpenRSI's review table.

## Research question

Can an autonomous researcher synthesize a reusable decentralized controller
that improves a frozen, pretrained three-agent team's coordination in Alem,
using only the information and communication actions already available to
each actor, without changing the environment or retraining the policy?

The submitted artifact is executable controller code, not a written plan. The
outer researcher forms a hypothesis, changes the controller, runs full worlds,
examines measured outcomes, and revises it. The three inner actors are recurrent
MARL policies with private controller memory. They are **not conversational
LLMs**. A researcher can itself be a single LLM agent or an LLM team; those are
separate, budget-matched research-trajectory comparisons.

## Fixed substrate

- Official MIT-licensed source: `alem-world/alem-env`, release v0.2.1, immutable
  commit `14d412e5ee961f9c43d6ce92ee05fee9cd1efc5e`.
- Public checkpoint: `alem-world/alem-rl-baselines`, Hub revision
  `9493179ea5e86cd625add66c0f88e23f04f928b5`,
  `1B/hypermarl-rnn/hard/seed0`. The selected training seed is fixed, not chosen
  by pilot score. Downloaded bytes are checked against the asset manifest.
- Three actors; Hard coordination settings; four native communication
  channels; action masking; official agent-ID conditioning; greedy masked
  categorical mode; unchanged recurrent forward pass and weights.
- Set `SCALE_BASE_DIFFICULTY=false` explicitly. This is the current release
  configuration used in our feasibility study. The old checkpoint's training
  config used true and an older environment, so historical scores are not a
  matched comparator.
- Normal 10,000 joint-transition episode limit, with natural termination when
  all actors die. No shortened episodes, favorable restarts, map edits, free
  inventories, hidden observation removal, or case selection by outcomes.

## Candidate interface

One `controller.py` is instantiated in three separate persistent workers.
`initialize(agent_id, schema)` returns private JSON memory. At each simultaneous
game step, `act(local, memory)` returns an integer legal action and updated
memory. The local packet contains only that actor's official observation
vector (including its official self-ID suffix), legal-action mask, frozen
masked logits and proposed action, its own previous reward, and the step.

The schema documents dimensions, action IDs, and observation layout. Public
renderer and game-rule source are available during research. Teammate data
already present in the official observation remains visible. The controller
may choose **any** legal action and may ignore the frozen proposal; there is no
top-k restriction or mandatory override quota. Private memory resets between
worlds. All three worker containers are recreated per world, resetting module
globals, private files and RNG state as well as declared JSON memory. The
frozen recurrent network advances on the actual observation every
step, including steps where the controller overrides its action.

Controllers cannot read peer packets, a shared writable file, world state,
world seed, environment RNG, future states, reward internals, or a simulator
oracle. Coordination uses only the four existing communication actions and
ordinary game actions. Communication costs a game turn, as in the native RL
interface. A centralized pooled-observation controller would be a separately
labeled information-advantage control, not part of the matched main track.

## Evaluation and feedback

The matched workload uses all 20 canonical Hard worlds, seeds
9999–10018, in a fixed order. Development worlds 20000–20003 are disjoint.
These seed ranges are public; do not describe them as secret test data. Local
controller processes never receive a seed. Test-time world recognition and
seed-specific action tables are prohibited; source review and development
transfer diagnostics check this, with residual overfitting risk acknowledged.
Because the simulator and seeds are public, the research process could regenerate
these maps. Seed omission does not prevent that. This is a fixed-workload
optimization task, not a protected unseen-world generalization evaluation.

The controller track resets transition RNG separately for each world under an
explicit formula: reset with `PRNGKey(world_id)` and start transitions with
`fold_in(PRNGKey(0xA1E00001), world_id)`, then the native three-way split at
each step. The official sequential evaluator carries RNG
between episodes, so changes to an earlier episode's duration otherwise change
later transition randomness. Our native 20-world run remains separate; a fresh
matched pass-through score is used for this controller track. Identical
random keys do not imply identical physical events after different actions.

Score is the arithmetic mean of the official per-world normalized
coordination reward fraction, on a 0–1 scale; larger is better. Report percent
by multiplying by 100, never as a binary success rate. Report base and total
reward, coordination subcategories, survival length, legal-action validity,
action-override fraction, communication usage, and resource cost alongside it.
These secondary quantities diagnose the mechanism; they do not silently
reweight the score.

All worlds must finish normally or reach the declared episode ceiling to
produce a score. Deaths and zero rewards remain in the mean. Candidate-invalid
syntax, exceptions, illegal actions, process crashes, or memory violations are
unscored. Timeouts, infrastructure faults and incomplete evaluations are also
unscored. Preserve their outcome records; never convert them into low model
reward or silently replace them. Each explicit retry is a separately logged
attempt and consumes research time.

Work can inspect its own development trajectories and run the simulator on
development worlds. Judge returns aggregate reward and bounded validity/cost
diagnostics, not full evaluation trajectories or per-world observations.
Normal Judge evaluations run the candidate only, using a fixed previously
measured matched pass-through reference. Solution materializes the released
checkpoint plus pass-through controller without training or evaluation.

## Research freedom and scientific controls

Candidate-owned code may implement local map memory, readiness/commitment
protocols, role-dependent plans, teammate motion prediction, stalled-plan
recovery, action selection and bounded controller-parameter search. It cannot
modify the frozen network, environment, metric, packet routing or evaluator.
Web search, external services, external data, online model calls from the
submitted controller, and test-time simulator lookahead are **disabled**.
The outer research agent itself is supplied by RSI-Harness; it is not a hidden
inner-controller service. Initial public source/checkpoint acquisition occurs
during task setup, before the offline research phase.

Development rollouts from world seeds 20000–20003 can be saved, inspected and
analyzed within Work. Additional collection outside those four development
worlds is disabled in this first task version. Offline planning and deterministic
parameter search over those development rollouts are allowed. No gradient
training, new checkpoints, evaluation-map regeneration, evaluation-trajectory
reconstruction or seed-specific action tables are permitted.

Controllers must be deterministic given their local input and private state.
If using a pseudorandom tie-breaker, initialize its seed to a constant recorded
in the candidate source, with optional agent-ID dependence, and reset it per
world. Wall clocks, OS entropy, persistent run counters and undeclared external
inputs are prohibited. Source inspection and replay detect ordinary violations;
this is a declared research boundary, not a proof against arbitrary malicious
programs or runtime tampering.

The essential matched baseline is the official policy passed through unchanged.
A simple scripted readiness/rendezvous controller is an additional useful
control. To attribute any improvement to coordination, inspect synchronization,
handover and construction outcomes, not just survival. To attribute improvement
to augmenting a learned policy, use a closed-loop controller-only/no-logits
ablation; a controller that replaces all decisions remains a valid optimization
artifact but is not evidence of useful pretrained-policy augmentation.

Fixed deterministic worlds allow precise within-workload comparisons without
ceremonial repeat runs. Variation across worlds describes task heterogeneity,
not training-seed uncertainty. Generalization beyond those worlds needs a
separately declared transfer check; no general claim follows from one fixed
checkpoint and one research trajectory.

## Integrity and resources

The local prototype separates the trusted simulator and three untrusted
controller processes with no-network, read-only containers and typed byte
messages. Generated controller code is never imported on the host. Record
source, checkpoint, image and candidate hashes before and after execution.
Only the trusted environment computes rewards.

The eventual RSI-Harness Judge loads the **complete Work snapshot**, with
task-owned tests injected Judge-only. It is not an independent clean-Base
verifier. Process isolation and hash checks are useful task safeguards, not a
proof against arbitrary-root modification of inherited runtimes or libraries.

The matched 20-world isolated pass-through took **278.79 seconds** including
container startup, imports, restore, JIT and teardown, for 8,489 joint steps.
Four development worlds took about two minutes. The engine is capped at four
CPU cores/6 GiB, and each of three workers at one core/512 MiB. Provision one
node with eight CPU cores and 16 GiB RAM for Work and Judge; both use zero GPUs.

The per-candidate operational ceiling is 10,800 seconds; per-worker replies
have a 30-second safety deadline. These are elapsed-time units and include
actual retries as separate runs. Natural deaths and the unchanged 10,000-step
world ceiling remain the only game termination rules. The 863-step pass-through
parity trial extrapolates to roughly 75 minutes for 20 maximally long worlds;
that is an estimate, not a measured slow-controller guarantee.

Plan 15–45 minutes of Work for candidate code/parameter experiments and roughly
5–90 minutes of Judge for one submitted controller: approximately 20–135 minutes
per change-run-feedback cycle. This estimate includes process overhead and
assumes controllers with moderate per-step CPU work. Under those assumptions,
48 hours / 2.25 hours gives about 21 complete loops before additional research
margin (and a 24-hour budget can accommodate ten at that conservative estimate).
Use a 24-hour research budget, extendable to 48 hours. These are planning
estimates, not promises of completed agent loops; slow or invalid candidates
may exhaust the operational ceiling. Work pauses during Judge. No parallel
candidate evaluations are counted as extra adaptive loops.

## Evidence and decision criteria

Native current-config baseline: 20/20 worlds completed; 18.9308% coordination,
15.5760% base, 16.9947% total normalized reward. This establishes executable
assets and headroom. It does not measure modern LLM researchers, prove a novel
coordination method, reproduce the historical paper score, or certify the
controller adapter.

The matched controller baseline completed all 20 worlds at **18.5220%**
coordination, 14.2627% base and 16.0638% total normalized reward, with zero
overrides and all provenance checks passing. Across-world sample SD is 4.8437
percentage points (range 6.9182–28.3019); this is world variation, not repeat-run
noise. Handover reward is already 85%, hard-sync 14.1477%, and construction 0%.
The latter is not by itself proof of failed available construction attempts.

Pass-through transport parity and per-actor information flow have been checked;
the fixed baseline and current controller contract are executable. Record
research-agent pilots with all attempts retained.
Never claim "most models fail" without actually evaluating those models.

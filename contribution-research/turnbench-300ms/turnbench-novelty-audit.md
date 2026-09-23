# TurnBench task novelty audit

Research date: 2026-09-23. Audit window: 2026-03-23 through 2026-09-23, plus foundational prior work. Public read-only research; no external writes, dataset access agreements, training, or execution of repository code.

## Proposed task and defensible novelty statement

**Task:** Improve a frozen, released VAP model using a small causal trainable decision head, trained on speaker-disjoint otoSpeech. Maximize timely interruption recall (committed event no later than 300 ms after gold onset, retaining TurnBench's 250 ms early tolerance) under one global decision policy whose interruption false-positive rate is at most 0.10 for every conversation type. Backchannels/noise remain negatives; non-floor-taking interruption exclusions remain as defined by the original benchmark.

No public exact match to the combination of a strict event-level 300 ms deadline, worst-conversation-type FPR constraint, and this frozen-VAP improvement task was found among the sources below. This is an original **constrained optimization task proposal**, not a claim that interruption detection, low-latency decision heads, onset classification, VAP adaptation, or robust optimization are new. A literature search cannot prove universal novelty.

## Crucial current-evidence correction

The August paper's 14 systems are no longer the whole live leaderboard. The [official TurnBench website](https://turnbench.sesame.com/) includes six external submissions as of this audit. Its public bundled leaderboard data gives the following interruption results:

| Submission | Submitted | Recall | FPR | Median committed latency |
|---|---|---:|---:|---:|
| SPX-AI MicroCF | Sep 13 | .984 | .073 | 747 ms |
| Vox Maru v1 | Sep 6 | .964 | .085 | 368 ms |
| Tavus Sparrow-2 | Sep 1 | .958 | .126 | 959 ms |
| Neosapience Nunchi v1 single-channel | Sep 2 | .939 | .049 | 666 ms |
| Neosapience Nunchi v1 dual-channel | Sep 2 | .899 | .078 | 1027 ms |
| Zero Runtime Echo Omni | Sep 10 | .904 | .129 | 698 ms |

The original VAP result is .945274 recall, .10749 FPR, 993.5 ms median. Its Casual/Spontaneous FPR is .128308. Do not describe VAP as currently the overall leaderboard leader; say it is the strongest of the paper's original baselines. Current commercial submissions often have high full-window recall.

**Derived, not measured:** Because the median true-positive delay exceeds 300 ms, approximately at most half those matched events could satisfy a 300 ms deadline at each published operating point. This bounds timely recall by about .473 for VAP, .482 for Maru and .492 for MicroCF. These are optimistic upper bounds, not reproduced scores or bounds after fair retuning. Rounding/quantile conventions add a tiny finite-sample correction. An event scorer should compute the actual metric, including clamped/overlapping matching windows.

A pooled FPR over .10 necessarily violates a <=.10 constraint in at least one nonempty type. Even when pooled FPR is below .10, the worst-type constraint is unverified without type-level scores. No claim is warranted about all possible parameter settings of any system.

## Exact baseline provenance

[TurnBench source pinned at 76ccd045f121ccfa921abac2ad3107027e736911](https://github.com/SesameAILabs/turnbench/tree/76ccd045f121ccfa921abac2ad3107027e736911).

[Baseline README](https://github.com/SesameAILabs/turnbench/blob/76ccd045f121ccfa921abac2ad3107027e736911/baselines/vap/README.md) and [predictor](https://github.com/SesameAILabs/turnbench/blob/76ccd045f121ccfa921abac2ad3107027e736911/baselines/vap/predict.py): VAP supplies 50 Hz near-future floor probabilities; interruption probability is `p_now`, forecasting 0–0.4 seconds. Default is already the **oto checkpoint**, with pretrained/oto/swbd/swbd_oto variants. The recorded oto thresholds are EOT .9161 and INT .8591, selected under pooled dev FPR<=.1. Thus simply fine-tuning on otoSpeech is not novel. The proposed head must be compared against fair retuning of the existing frozen probability/commit policy under the new objective.

## Closest current systems

### Maru v1 — the most important close comparator

[Author's September 11 write-up](https://medium.com/@sjhan99/turn-taking-maru-v1-on-turnbench-687745c0e4a7).

Maru runs causal Silero VAD plus a shared two-channel Whisper-tiny onset classifier over a 4-second context. Decisions are made at .2,.4,.6,.8,1.0 seconds after onset; six classes include backchannel and floor-taking interruption. Training uses only otoSpeech, with 10% conversation-held-out checkpoint selection. Interruption commits at the earliest qualifying horizon or after a duration fallback. The operating point maximizes pooled dev recall under FPR<=.08, with split-repeat optimism checks. It reports prefix-truncation causality checks.

**Difference:** It already implements early learned onset classification with backchannel negatives. The proposed contribution must distinguish its strict 300 ms recall and every-type FPR objective, restricted frozen VAP representation, and reproducible open improvement loop. Do not claim the first early floor-claim classifier.

### MicroCF — current top interruption recall, already modifies frozen VAP policy

[Author's project write-up](https://spx-ai968.github.io/microcf/) (read successfully through direct public HTTPS; web tool returned an access error).

MicroCF combines FunASR VAD with VAP and retains the underlying checkpoints. Its new streaming state machine uses activation persistence, release confirmation and interruption duration thresholds. One fixed policy applies to all conversations. INT policy selection minimized FPR among settings with recall>=.97 and median latency<=900 ms; its reported full-dev score is .9856 recall/.0705 FPR/771 ms. The write-up discloses reused dev subsets and does not represent them as pristine held-outs.

**Difference:** Same backbone-family/policy space, but no trainable decision head or per-type FPR constraint is described; median <=900ms rewards a substantially different failure profile from per-event <=300ms. Pure threshold/state-machine changes alone would overlap strongly with this work and be a weak novelty argument.

### Ooma description — VAP pretraining plus causal small MLP already proposed

[Model card](https://huggingface.co/ooma-ai/turn-detector).

Describes a streaming FastConformer feature encoder continued with VAP pretraining, a small MLP using target and joint speaker state, causal VAD gating and a 160 ms commit grid. It names TurnBench with deadline/FPR evaluation, but says weights are unpublished. It appears focused on end-of-turn decisions. No worst-type FPR requirement is described.

**Difference:** General VAP-derived encoder plus causal MLP is prior art. The task should not make an architecture-first novelty claim.

## Research in the preceding six months

- [FastTurn, April 2, arXiv 2604.01897](https://arxiv.org/html/2604.01897v1), [official repository](https://github.com/ASLP-lab/FastTurn): streaming CTC plus acoustic/semantic fusion and MLP turn decisions; handles backchannels. Reports classification accuracy and inference latency on segment datasets, not TurnBench event recall under worst-type FPR. Its ~120 ms latency is not directly comparable with committed-event delay from annotated onset.
- [ASPIRin, April 11, arXiv 2604.10065](https://arxiv.org/html/2604.10065v1): GRPO optimizes a projected speech/silence action policy using temporal rewards, balancing interruption and response latency. Thus separating timing decisions from language generation is also established. This is whole full-duplex model alignment, not the proposed small VAP detector task.
- [Multi-Faceted Interactivity Alignment, June 9 / revised August 28, arXiv 2606.11167](https://arxiv.org/html/2606.11167v2): GRPO across pause handling, turn-taking, backchanneling and interruption, with semantic preservation. Uses Moshi and PersonaPlex; releases checkpoints. Again, broad interaction reward optimization is existing work.
- [Duplex Cue, September 11, arXiv 2609.13117](https://arxiv.org/html/2609.13117v1): distinguishes listener intent (backchannel, collaboration, interruption) from speaker response (continue, adapt, yield). It warns that always yielding quickly is not universally human-like. Scope the proposal to **TurnBench floor-taking interruption detection**, not the claim that every overlapping utterance should immediately silence an agent. Do not merge collaboration into true interruption labels.

Older foundation: [An Incremental Turn-Taking Model with Active System Barge-in, SIGDIAL 2015](https://www.cs.cmu.edu/~awb/papers/W15-4606.pdf) already formulates incremental floor-taking as optimal stopping. [Rubato public source](https://github.com/NagaYu/rubato) also describes calibrated silence-survival forecasting plus asymmetric-cost stopping. A survival/optimal-stopping head is a plausible mechanism but not a new general principle.

## Proposed falsifiable mechanism

Hypothesis: Near-future floor probability alone is trained to forecast activity rather than optimize earliest reliable floor-claim detection. A compact temporal decision head over frozen causal VAP states/history, trained on event labels with early positive weighting and matched backchannel negatives, can improve deadline recall at the same per-type FPR limit. Compare with (1) original commit logic, fairly retuned; (2) a static probability logistic head; (3) the temporal head with ordinary loss; (4) early/event-level loss plus worst-group constraints. Head training, feature selection and head capacity are the iterative research space. Keep the hypothesis falsifiable; adding complexity may not beat retuning.

This suggestion does not require a particular fashionable method such as RL. A small causal convolution or recurrent head can test whether onset evolution contains useful evidence without paying the late confirmation times of a duration rule. No future context, annotation-derived runtime inputs, per-conversation overrides, or post-hoc timestamp shifts should be allowed.

## Evaluation details to settle before claiming success

- Preserve official event exclusions, one-to-one matching and negative-span accounting. Reduce the allowable late matching horizon to .300 seconds, rather than merely filtering a latency list produced by a three-second matcher if that changes event assignment.
- Count a late decision as a miss for the headline recall; publish full-window recall and latency distribution as secondary diagnostics.
- Fix whether the task requires empirical per-type FPR<=.1 or a confidence-bound guarantee. These differ sharply with rare event counts. Do not advertise a statistical guarantee based only on a point estimate.
- Keep conversation type out of runtime inputs unless explicitly allowed; one global policy should satisfy all groups. Use type for validation/scoring, and only for training loss if labels genuinely exist in allowed training data.
- Separate threshold-selection dev data from the final OpenRSI held-out evaluation; repeated public-dev optimization alone can overfit 38 conversations.
- Obtain and record actual score under the new constraint before asserting the benchmark baseline. Published medians only establish headroom, not the exact new score.
- Wall-clock inference and playback cancellation remain distinct from audio-time committed-event delay. Include causal preprocessing/chunk buffering in event timestamps and publish runtime separately.

## Search record and limits

Queries included TurnBench+300ms; TurnBench+worst+latency; interruption/backchannel low-latency 2026; turn-taking+worst-group/group-DRO/distributionally-robust; VAP+decision-head; interruption+300ms+false-positive; and optimal stopping turn-taking. Reviewed the official current leaderboard, current submission write-ups, arXiv papers and public source/model cards. Several unrelated benchmarks also use the name TurnBench and were excluded. Commercial/private implementations cannot be ruled out. No exact public task duplicate found; adjacent approaches are substantial and should be acknowledged prominently.

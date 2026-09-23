# Detect interruptions within 300 ms without mistaking acknowledgments for interruptions

Research prepared on 2026-09-23 for an OpenRSI contribution from the personal GitHub account **y12uc231**.

**Status: rejected direction. The contributor excluded speech tasks on 2026-09-23. This research is retained only as history; it will not be submitted.**

Previous research status: not a submitted or approved proposal. Publication metadata, contributor confirmation of the selected project, approved dataset access, and available compute remain unresolved. No training or model evaluation has been run. Once these are resolved, the final proposal should use the repository's exact [Section / Field / Proposal template](../../.agents/skills/proposal-agent/references/proposal-template.md), preserving every row and its order. Do not submit this research note as that proposal.

## The task

Teach a small causal decision model to recognize a genuine floor-taking interruption within 300 milliseconds, while triggering on no more than 10% of the annotated backchannel/noise negatives **in each of the six conversation styles**. A system should distinguish “mm-hmm, keep going” from “wait, I need to speak,” using only information already available at the moment it commits.

The proposed source is [TurnBench](https://github.com/SesameAILabs/turnbench/tree/76ccd045f121ccfa921abac2ad3107027e736911), coauthored by Satyapriya Krishna. The frozen reference model is the released otoSpeech-finetuned Voice Activity Projection (VAP) checkpoint. The research agent develops and trains a small decision model over its causal probability streams, measures the result, revises its hypothesis, and repeats.

**Falsifiable question:** Does temporal evidence in a frozen VAP model's probability history improve early interruption detection beyond scalar threshold calibration and a comparably trained memoryless head, under the same event decoder, supervision, and evaluation constraints?

This is a model-development research loop. It allows experiments on additional head memory, event-level training objectives, and hard-negative sampling; it is not a request to implement a detector once or merely reproduce a paper. A negative finding—that a simple calibrated threshold performs just as well—would also answer a meaningful question.

## Why this is a strong candidate

- The public OpenRSI audit found no speech or turn-taking task among **14 current task directories, 42 Task Ideas discussions, 337 top-level discussion comments plus 2 replies, and 67 all-state PRs**. One additional Q&A discussion was also reviewed. See the [complete catalog audit](catalog-audit.md).
- The problem is current: TurnBench was released in August 2026 and revised in September. The [live leaderboard](https://turnbench.sesame.com/) includes newer systems beyond the original paper.
- Public code supplies event construction, exclusions, matching, checkpoint loading, predictions, and fixed split IDs. This supports an auditable task rather than an invented evaluation story.
- [The contributor's public profile](https://satyapriyakrishna.com/) and [TurnBench author list](https://arxiv.org/abs/2608.25218v2) establish relevant expertise. The coauthored-project route still needs the contributor's confirmation; no publication email has been inferred from public pages.

### Evidence of the unresolved performance tradeoff

These are **published test results, not reproduced measurements**. The new task's actual development-set score is not yet known.

| System | Full-window interruption recall | Negative-span FPR | Median detection delay |
| --- | ---: | ---: | ---: |
| SPX-AI MicroCF, current external submission | 98.4% | 7.3% | 747 ms |
| Vox Maru v1, current external submission | 96.4% | 8.5% | 368 ms |
| VAP, released reference | 94.53% | 10.75% | 993.5 ms |
| ESPnet Turntaking, faster paper baseline | 57.34% | 7.98% | 210 ms |
| OpenAI Realtime Server VAD, paper baseline | 99.01% | 45.83% | 183.5 ms |

Sources: the live site's **Interruption** tab, checked on 2026-09-23, and the pinned [`results/leaderboard-test.json`](https://github.com/SesameAILabs/turnbench/blob/76ccd045f121ccfa921abac2ad3107027e736911/results/leaderboard-test.json). VAP's Casual/Spontaneous FPR is 12.83%, despite its pooled operating-point calibration.

The high full-window recalls must not be described as poor overall performance. The weakness is the simultaneous requirement for speed, recall, and low false alarms. A median above 300 ms means roughly half or more of the matched detections are later than the proposed deadline. At the published operating points, this implies approximate timely-recall upper bounds of 49.2% for MicroCF, 48.2% for Maru, and 47.3% for VAP. These are **derived bounds**, subject to rounding and finite-sample quantile conventions, not measured task scores and not bounds after retuning. The exact task-aligned baselines must be measured before asserting how much improvement is available.

## What is distinctive—and what already exists

The defensible novelty is the **specific OpenRSI improvement task and constrained objective**: reward only early matched detections, apply the false-positive ceiling to every conversation style, and test temporal evidence against matched simple controls on a fixed released representation.

No exact public duplicate was found in the reviewed catalog and literature. This cannot establish that nobody anywhere has tried it, and the architecture family is not new.

The closest existing work is substantive:

- [Maru v1](https://medium.com/@sjhan99/turn-taking-maru-v1-on-turnbench-687745c0e4a7) already trains a causal onset classifier on otoSpeech, with decisions starting at 200 ms. Its reported operating point optimizes full-window recall under pooled FPR.
- [MicroCF](https://spx-ai968.github.io/microcf/) already changes a frozen VAP-based temporal policy. Its described interruption selection prioritizes FPR subject to high recall and a median-delay limit of 900 ms.
- [FastTurn](https://arxiv.org/abs/2604.01897), [Multi-Faceted Interactivity Alignment](https://arxiv.org/abs/2606.11167), and [Duplex Cue](https://arxiv.org/abs/2609.13117) already study closely related causal decisions, interaction rewards, and listener intent.

See the [novelty audit](turnbench-novelty-audit.md). The evaluation definition below resolves the audit's alternative matching suggestions: **retain the official matcher, then count its timely matches**. This is an explicit new metric, not an assertion that it equals rerunning the matcher with a shorter window.

## Proposed evaluation contract

### Workload and assets

Use all **38 conversations** in the pinned public development split, approximately 7.3 hours. The pinned scorer documentation reports **347 interruption positives and 3,733 interruption negatives**. Preserve majority agreement, exclusions, speaker attribution, and the fixed split. Validate those counts from the actual assets before execution; do not silently replace inaccessible, corrupt, or missing conversations.

The official test audio has no public labels. **The task does not depend on that private test set, an email scoring service, or any Sesame internal asset.** The released development set becomes the fixed OpenRSI evaluation set. Its labels are withheld from the research workspace, but their public availability and previous use for published threshold tuning are residual limitations, not secrets we can guarantee.

Train candidate decision models on otoSpeech only. Define and freeze a conversation-level training/calibration partition before the first scored candidate, using the actual verified metadata. Do not claim speaker separation within this partition unless the delivered metadata supports it. TurnBench documents otoSpeech as speaker-disjoint from the benchmark. Training-set conversation-type labels have not been verified; the design must not assume them or require group-labelled training losses.

### Metric

Run the pinned official `score_task` unchanged, including the **−250 ms annotation tolerance, +3 s matching window, one-to-one attribution, exclusions, and negative-span FP accounting**. Let `N = TP + FN` and let `L` be the latencies of its matched interruptions.

```text
R300 = count(l in L where l <= 300 milliseconds) / N
FPR_g = FP_g / (FP_g + TN_g), separately for each of the six styles
FPR_worst = max_g FPR_g
score = R300 if FPR_worst <= 0.10, otherwise 0
```

Score is dimensionless in [0,1]; higher is better. Aggregate counts across speakers and conversations before dividing. This is **deadline-qualified recall under official matching**. Merely setting `tau_max_s=0.3` would also alter FP exemptions and matching; that is a different protocol and must not happen accidentally.

All six groups must have verified negative denominators. A missing required group is an evaluation/setup failure, not permission to omit it. A valid policy exceeding the empirical FPR ceiling gets zero. A valid silent policy gets zero recall. Malformed, noncausal, or crashing artifacts—including attributable compilation failure or illegal memory access—are unscored. Infrastructure failures, timeout, and incomplete evaluations are unscored rather than fabricated finite results.

The constraint is an **observed dataset rate**, not a population guarantee. This metric measures false alarms on annotated Backchannel/NonContent spans, not all false interruptions per hour.

### Matched reference and controls

1. **B0: released VAP threshold under the task’s clock.** Materialize the released oto checkpoint and documented interruption threshold `0.8591`, with official event commitment. Solution assembles this reference without training or evaluating it. Its original threshold was chosen for a different objective, so beating B0 alone is insufficient scientific evidence. Any availability delay required by the causal extraction audit is charged to this reference too; the resulting timestamps must not be described as exact reproduction of the published ones.
2. **B1: calibrated scalar policy.** A Work-produced control using the same frozen streams and commitment decoder, with threshold calibration under the declared training/calibration protocol. It tests how much gain comes from ordinary recalibration.
3. **B2: memoryless trained head.** A Work-produced control trained on the same allowed labels, features, and compute allowance as the temporal candidate. It tests whether added supervision explains a gain. VAP features already contain temporal context; this control is memoryless only at the downstream head.
4. **Candidate: causal temporal head.** Compare against both controls. Ablate additional head memory and early-event loss separately when those mechanisms are claimed to help.

The precise training/calibration manifest and calibration objective must be frozen after verifying the training metadata. All controls and candidates face the identical judge metric; do not access or tune on per-example Judge outcomes; aggregate feedback may guide subsequent candidates. Normal candidate evaluation is candidate-only; baseline and control scores are retained, not rerun as paired training on every submission.

### Causality and final deliverable

Proposed inputs are fixed VAP `p_now` and `p_future` streams for both speakers, produced by one pinned extraction pipeline. Audit the encoder, resampling, frame alignment, and chunking before accepting these as causal. An offline forward pass is not sufficient evidence. Use prefix-invariance checks and charge buffering/lookahead to the feature's availability time.

The candidate supplies a small trainable causal policy, weights, and configuration. Judge feeds current/past features sequentially and owns the clock. It supplies no conversation ID, type, final duration, annotations, future features, or candidate-controlled event timestamps. Reset state between conversations. Fix the official rising-edge commitment convention and **2-second refractory** identically for B0, controls, and candidates.

The backbone, audio preprocessing, feature definitions, event decoder, datasets, and scorer are fixed. The research space includes temporal head architecture, causal memory, training objective, and training-only negative sampling. Record a head-size bound and per-candidate train exposure/compute budget in the final proposal after available hardware is known. Prohibit per-example lookup tables, evaluation-content training, timestamp shifts, type-specific runtime overrides, altered judges, and self-reported reward files.

### Feedback, uncertainty, and limits

Return score, R300, full-window recall, each type's FPR and denominator, constraint margins, latency quantiles, and total commitments per audio hour. Do not return individual evaluation examples, timestamps, labels, or error traces containing them. Detailed training/calibration diagnostics remain available.

Fixed-artifact evaluation is deterministic enough that repeated runs are not automatically required. There are only 347 documented positive events, so the same-conversation pairing and event-count changes matter. After baseline reproduction, examine conversation-clustered uncertainty and repeat training only if observed variability can change the conclusion. Report annotation tolerance and deadline sensitivity as diagnostics without changing the primary score after seeing outcomes.

Repeated aggregate feedback on 38 public conversations can overfit. Restrict network/data access, scrub prediction/gold files from Work, log all judged candidates, and report that limitation. The current RSI-Harness evaluates a complete Work snapshot with task-owned tests injected in Judge. It is **not an independent clean-Base verifier**; inherited runtime tampering remains a platform limitation. Controls must be realistic under that model.

## Public provenance and access status

| Asset | Immutable revision or evidence | Status |
| --- | --- | --- |
| OpenRSI guide/skill/template | `5d411876624e78b84499e2759b50febbf8cf75a7` | Read; cloned locally |
| TurnBench source | `76ccd045f121ccfa921abac2ad3107027e736911` | Public; inspected locally |
| VAP oto checkpoint | [viks66/VAP_checkpoints](https://huggingface.co/viks66/VAP_checkpoints/tree/b9aa0ba1718221153e04ef343c7f3b8cf84bfbc3), `oto.ckpt` | Public, ungated; API reports CC-BY-4.0 |
| VAP implementation | [ErikEkstedt/VoiceActivityProjection](https://github.com/ErikEkstedt/VoiceActivityProjection/tree/f39a78b23a6dccdbedd106e00b48c410b8739f5d) | Public commit resolved; checkpoint compatibility and causal extraction remain execution checks |
| Evaluation data | [mundo-ai/turn-benchmark-dev](https://huggingface.co/datasets/mundo-ai/turn-benchmark-dev/tree/8fa18a24be51528a45397b35cbcaecd84202062b) | Gated; this is the revision pinned in `turnbench/data.py`, not current HF main |
| Training data | [otoearth/otoSpeech-full-duplex-turn-104h](https://huggingface.co/datasets/otoearth/otoSpeech-full-duplex-turn-104h/tree/46f520297f434edf804389f82f9075a59d2f8268) | Gated; contributor access not confirmed |
| Published results | `results/leaderboard-test.json`; live interruption leaderboard | Read; not reproduced |

The data has a separate noncommercial license prohibiting voice cloning; no dataset agreement has been accepted on the contributor's behalf. The concrete delivery path is authenticated Hugging Face snapshot download at the named revisions, contingent on approved access and applicable use. No unspecified private bundle is assumed. Web search and external model services should be disabled during research; setup may fetch only the pinned dependencies/assets. Do not place access credentials in the proposal, repository, or trajectories.

Important source paths: `baselines/vap/{README.md,predict.py}`, `turnbench/{README.md,data.py,gold.py,score.py,sweep.py,submission.py}`, `turnbench/splits/dev.txt`, `docs/SUBMISSION_FORMAT.md`, and `results/leaderboard-test.json`. The existing launch path is `baselines/vap/predict.py`, with explicit local checkpoint and fixed thresholds; ordinary scoring is `python -m turnbench.score predictions.json`. The proposed R300/group aggregation and streaming Judge wrapper are task-owned adaptations to these verified primitives, not existing upstream commands.

## Compute plan to confirm

Proposed lane: **one machine, one GPU**, 16 CPU cores and 64 GB RAM as provisional planning estimates. H100 is the budgeting reference, not a required model; compatible hardware may suffice. Exact available hardware is unknown.

Freezing VAP permits reuse of training features across head experiments. Nevertheless, extracting 104 hours of training features is a real one-time cost. Judge should recompute the fixed 7.3-hour evaluation features unless a supported, protected cache is demonstrated; do not assume hidden caches survive the harness lifecycle.

An illustrative budget, **not measured or contributor-confirmed**, is 30–60 minutes of Work head training plus 30–60 minutes of Judge inference/scoring plus 10 minutes of transfer/overhead: **70–130 minutes per cycle**. `48 hours / cycle` is approximately **22–41 optimistic cycles**, before one-time extraction and research time. At an explicitly assumed 10–20x realtime, initial training feature extraction would itself take approximately 5.2–10.4 hours. These assumptions need validation. Use a 24-hour initial research budget, normally extendable to 48 hours; aim for at least ten complete adaptive loops with operational margin. Current status: **Estimate incomplete**.

Charge failed attempts, repeated training, replacement candidates, feature recomputation, and mandatory transfer to the wall-clock budget. A retry of the same candidate is not another adaptive research loop. Halt on NaN, divergence, OOM, causality failure, or execution failure; do not silently omit evaluation data or shrink the workload.

## Remaining contributor inputs before the formal proposal

1. Full professional name and the exact publication email the contributor wants published. Publicly scraped contact information cannot fill this field.
2. Confirmation that TurnBench is an appropriate coauthored project for this contribution and that the contributor chooses this research direction.
3. Approved access to both named HF datasets for this use, or a concrete existing usable delivery. The private official test labels are not needed.
4. Available GPU, CPU cores (if applicable), RAM (if applicable), and a realistic runtime estimate or approval of the clearly labelled planning estimates after hardware is specified.

The final scientific contract should then freeze the training/calibration manifest, feature interface, control protocol, and compute limits; fill the **exact official table**; perform the nine-gate review; show the completed proposal for review; and create one Task Ideas Discussion from the reviewed file using `y12uc231` authentication. The upstream workflow builds a private task repository after passing review. A fork PR is not the proposal submission path.

## Research package

- [Full OpenRSI coverage and duplicate audit](catalog-audit.md)
- [TurnBench closest work, timing evidence, and novelty limits](turnbench-novelty-audit.md)
- [D-REX investigation and why it was not selected](drex-research.md)
- [FRAMES fallback and other source investigations](alternative-research.md)

Only public research evidence is included here. Nothing has been submitted to the upstream Discussion, no email has been sent, and no acceptance or completed evaluation is claimed.

# D-REX feasibility and novelty audit

Research date: 2026-09-23. Read-only research; no credentials used, external writes, training, or repository execution.

## Decision

D-REX is not presently a defensible self-contained OpenRSI task source. Do not imply a runnable baseline, public split/checkpoint, or current detector failure that was not verified. User authorship of a paper does not establish permission to publish private research data.

## Verified D-REX facts (official paper)

[Official paper, pinned arXiv v1](https://arxiv.org/html/2509.17938v1), published 2025-09-22, reports 8,162 transcripts from competitive red-teaming across seven behaviors and seven models. Appendix D explicitly keeps the data private: teams submit models to a forthcoming website; evaluations return aggregate metrics, excluding generated outputs and reasoning traces. No public official repository, downloadable train/evaluation split, detector checkpoint, or source commit was located in searches.

Table 2 measures target models' susceptibility to attacks, not detectors' classification accuracy. Target-specific attack success spans 28.22% (Nova Pro) to 42.01% (Qwen3-235B); random-pool vulnerability spans 0.20% (Nova Pro) to 42.05% (Gemini 2.5 Pro). These are 2025 model versions, not evidence of September 2026 frontier weakness. Four judge models supply criterion scores, with minimum score used. The paper proposes monitoring as a secondary use rather than benchmarking a trained monitor.

Appendix E proposes broader tool-use and exfiltration settings. Adding those alone is therefore an explicit future direction, not a defensible claim of unprecedented novelty.

## Close work inside 2026-03-23 to 2026-09-23

### Hard negatives and monitor cascade already exist

[Probing the Misaligned Thinking Process of Language Models](https://arxiv.org/abs/2606.24251), [official project](https://probe-misalignment.github.io/), [official source](https://github.com/safety-research/misalignment-indicators), [dataset](https://huggingface.co/datasets/kzhou35/misalignment-indicators-bloom-rollouts).

This work trains 18 indicator probes with synthetic multi-turn hard negatives and benign controls, reporting probe AUROC 0.936 and cascade AUROC 0.950. The second-stage verifier specifically addresses cases where a model considers a malicious plan then rejects it. Therefore “hard-negative contrastive monitors that distinguish harmful discussion from commitment” would substantially overlap known work. This source looks runnable, but reported aggregate performance is already strong; a constrained new objective would need its own baseline.

### Most directly relevant recent failure evidence has caveats

[Fine-Tuned Lie Detectors Failed to Generalize](https://alignment.anthropic.com/2026/lie-detectors/), dated 2026-08-21, [released dataset](https://huggingface.co/datasets/Noddybear/lies).

Gemma3 detector fine-tuning achieves around 0.95 in-distribution AUROC but only 0.70–0.75 on unseen lie categories. Importantly, Qwen3-235B prompting reaches 0.98–0.99; this refutes an unqualified “existing models do poorly” claim. Labels are imperfect and roughly 25% changed during judge-based cleanup. Public data is MIT-licensed and the dataset viewer exposes train/test splits, approximately 136K train rows, source model, fold, trace and binary did_lie fields. A split audit and baseline reproduction would be required before an OpenRSI proposal. The source used LoRA r=16, alpha=32, dropout=.05, final-token cross entropy, five epochs, about 5,000 examples/fold, and balanced 50/50 lie-type held-outs.

### Better-released transfer evaluation, still not easy evidence for all models

[“Did you lie?” Evaluating Lie Detectors across Model Scale and Belief-Verified Model Organisms](https://arxiv.org/html/2606.12618v1), [official artifact collection](https://huggingface.co/collections/ai-safety-institute/lie-detection).

The June 2026 paper releases datasets, organisms and trained detectors. It reports median balanced accuracy decreasing from 0.81–0.85 on prompted lies to 0.50–0.65 on 13 trained organisms for activation/logprob detectors; CoT judging remains at 0.82. The authors explicitly warn that verification favors CoT-readable beliefs. A transfer task built from released detectors could be viable, but would need exact artifact checks, training/test isolation, and current baseline reproduction. No artifact commit was verified in this subtask.

### Other related mechanisms

[Persuasion Attacks Can Decrease Effectiveness of CoT Monitoring](https://arxiv.org/abs/2607.08066), 2026-07-09, reports that access to adversarial scratchpads can increase approval of policy-violating actions by 9.5%; cross-family fact checking helps. This makes a generic fact-checker-before-monitor proposal an existing mechanism.

[Contrastive representation learning for self-supervised deception detection in edge LLMs](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0354894), August 2026, uses triplet-loss monitor learning and iterative refinement, plus a frozen monitor for policy optimization. Thus contrastive monitor training itself is not novel. Its reported task is deception tendency mitigation, not detector AUROC; do not equate those metrics.

## Falsifiable research hypothesis if private D-REX rights and artifacts are later provided

Proposed hypothesis, not claimed novel: A compact monitor trained to separate adopting a malicious goal from quoting, rejecting, or correcting it will improve worst-held-out-behavior recall at a predeclared low false-positive rate compared with a matched-capacity classification baseline. Group all derivatives of a red-team prompt and all paired contexts in one split; train only on public training examples; lock final labels and thresholds before hidden evaluation. Include per-behavior performance and confidence intervals, and treat the largest prompted monitor as a ceiling comparator. This remains conditional on rights, data, annotation consistency, and a novelty search covering the exact representation and optimization objective.

## Search audit and limits

Queries included exact paper title and arXiv identifier plus GitHub/data/checkpoint; D-REX deceptive-reasoning 2026; CoT monitors with hard negatives; deception detector generalization; and date-filtered 2026-03-23 to 2026-09-23 searches. Same-name D-REX robotics and dialogue-relation-extraction projects are unrelated. Searches can establish no close match found among reviewed public sources, never universal novelty. D-REX HTML snapshot saved separately only as research provenance, not as a publication deliverable.

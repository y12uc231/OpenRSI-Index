# Independent alternative research — 2026-09-23

## Best feasible ungated fallback

**Complete-evidence reranking for FRAMES: learn a compact set selector that preserves all required sources under a fixed passage budget.** This is a model-development experiment (train the selector/reranker and compare matched loss/conditioning treatments), not simply a new answer prompt. It is grounded in Satyapriya Krishna's first-authored [FRAMES paper](https://aclanthology.org/2025.naacl-long.243/) and the new official [MLCommons implementation](https://github.com/mlcommons/inference/tree/3fbc329939999c13d0a7b5e67fb2092287e06047/e2e-rag).

The scientifically strongest form changes only how an existing neural reranker selects a *set* of passages: can conditioning a passage's utility on already selected evidence improve complete required-source coverage, compared with independent relevance scores, while keeping passage count, candidate pool, training exposures, encoder, corpus and scorer fixed? The null is that diversity/conditioning only trades one source for another, with no useful increase in complete coverage. A matched independently-scored control is needed to attribute gains to the mechanism rather than extra training.

**Readiness:** strong research direction and public artifact base, but not a fully confirmed proposal. The parent should not represent the new complete-coverage score, split, runtime, or baseline quality as measured. A concrete task-owned evaluator adapter and predeclared dataset partition are still required. The user would need to confirm this scientific scope and compute, as with every proposal.

## Current poor-performance evidence

MLCommons' [August 26, 2026 announcement](https://mlcommons.org/2026/08/endtoend-inference/) reports its full FRAMES pipeline at **35% answer accuracy**, with **31% numerical** and **31% tabular** accuracy; aggregate retrieval recall is **70%**. That reference uses GPT-OSS-120B, GPT-OSS-20B, E5 and ColBERT, and explicitly acknowledges Satya's guidance. This is fresh evidence of a concrete pipeline weakness, not proof that every contemporary model fails FRAMES. It is also **not a score on our proposed reranking objective**.

The [original FRAMES paper](https://aclanthology.org/2025.naacl-long.243/) reports 0.40 no-retrieval accuracy and 0.66 with iterative retrieval. Those historical results should not be used as claims about current frontier models. The new MLCommons evidence is preferable.

## Verified public assets and pinned revisions

Read-only GitHub/Hugging Face metadata was inspected without logging into any additional GitHub account. No remote code, model, evaluation, or training was executed.

| Asset | Verified revision | Availability |
| --- | --- | --- |
| `mlcommons/inference` | `3fbc329939999c13d0a7b5e67fb2092287e06047` | Public Apache-2.0 source |
| `google/frames-benchmark` | `58d9fb6330f3ab1316d1eca12e5e8ef23dcc22ef` | HF API gated=false; Apache-2.0 |
| `intfloat/e5-base-v2` | `f52bf8ec8c7124536f0efb74aca902b2995e5bcd` | HF API gated=false; MIT |
| `colbert-ir/colbertv2.0` | `c1e84128e85ef755c096a95bdb06b47793b13acf` | HF API gated=false; MIT |
| `openai/gpt-oss-120b` | `b5c939de8f754692c1647ca79fbf85e8c1e70f8a` | HF API gated=false; Apache-2.0; optional downstream diagnostic |
| `openai/gpt-oss-20b` | `6cee5e81ee83917806bbde320786a8fb61efebee` | HF API gated=false; Apache-2.0; optional downstream diagnostic |

[MLCommons data portal](https://inference.mlcommons-storage.org/index.html) publishes the frozen FRAMES corpus bundle through `https://inference.mlcommons-storage.org/metadata/frames-benchmark-dataset.uri`. It contains the questions and a frozen 2,515-page HTML corpus. The download metadata and final files must be hash-pinned during packaging. Do not re-scrape live Wikipedia. The [repository README](https://github.com/mlcommons/inference/blob/3fbc329939999c13d0a7b5e67fb2092287e06047/e2e-rag/README.md) documents corpus extraction and index construction.

Important exact repository paths:

- `e2e-rag/retrieve/ragdb.py`, `retrieve/vectordb.py`, `retrieve/filter.py`: retrieval and score filtering.
- `e2e-rag/reranker_worker.py`: ColBERT reranking service.
- `e2e-rag/read_docs.py`, `text_splitter.py`, `measure_indexing_with_chunking.py`: corpus parsing/index construction.
- `e2e-rag/multi_shot_retrieval.py`: relevance grading, sufficiency checking and iterative retrieval. `multi_shot_retrieval()` starts around line 1181; it uses `evaluate_document_relevance`, `check_sufficiency` and per-subquery reranking.
- `e2e-rag/accuracy_eval.py`: `calculate_retrieval_metrics()` computes URL-set precision/recall/F1. Complete-set coverage is a clearly declared extension, not an existing upstream reported metric.
- `e2e-rag/reference_mlperf_accuracy.sh`: exact end-to-end launch path. The published pipeline uses 20B grading and 120B query/sufficiency/answer generation.

Local read-only snapshots of the main evidence files are in `research/mlcommons-source/`.

## Suggested bounded task design (proposed, not measured)

1. Freeze the HTML snapshot, parser, chunker, E5 encoder/index and label-blind candidate-pool construction. Use only the released FRAMES URL requirements as supervision. No new human or API-generated labels are required.
2. Use a deterministic partition of the 824 question records into train/development/final portions. The partition algorithm and counts need to be fixed before seeing results, with source-overlap statistics reported. Do not claim semantic generalization if the same article appears in train and final; consider source-group partitioning only if cardinalities remain viable.
3. Baseline is released ColBERTv2.0 pointwise scores over the same candidate pools, materialized without training by Solution. Its full implementation/artifact can be reloaded for direct evaluation.
4. Work may train a small set-conditioning head and/or fixed-schema adapters to the reranker, change the learning objective for complete evidence coverage, and form matched independent-scoring training controls. Frozen pool, input text, permissible model size, passage budget, exposures and inference FLOP/latency cap stay fixed. Agent produces a loadable model plus a deterministic selection manifest.
5. Judge runs the fixed reranker/selector API and derives scores from actual selected passage IDs. Primary metric: fraction of questions for which every released required-source URL is represented within the fixed budget. Secondary metrics: mean URL recall, mean precision, all-source coverage conditional on pool completeness, and stratification by source count/reasoning category. Count impossible-pool queries in the main denominator; conditional score is diagnostic only. Verify budget feasibility from source cardinalities before fixing K.
6. No claimed answer accuracy benefit without a downstream frozen-generator diagnostic. URL requirements can include redundant sources, and a page-level hit does not prove the passage contains the needed fact; explicitly report these proxy limitations. A natural future extension measures sentence-level evidence and end-to-end accuracy.
7. All assets prepared before Work. Work/Judge network disabled. Candidate cannot edit data, pool construction, evaluator, labels, decoding/scoring, or load an answer/URL lookup table. Judge injects tests into the complete shared candidate snapshot; it is not an independently clean Base.

Compute proposal: **one physical node, one H100 80GB, 16 CPU cores, 128GB RAM** for Work; approximately 45–90 minutes for a bounded compact-reranker trial after one-time data/index setup. Judge one H100 and approximately 10–30 minutes. **Estimated complete cycle 1–2 hours, not validated.** A CPU-only Judge may be feasible for cached representations plus a small set head, but should not be promised without checking. This avoids 120B rollouts and any gated judge, and makes ten research loops plausible.

For a richer end-to-end alternative, keep GPT-OSS models frozen and optimize the selector within the live five-hop pipeline. That is scientifically stronger but less predictable in runtime. The full published launcher sets `JUDGE_MODEL=meta-llama/Llama-3.1-8B-Instruct`; its access is not established. `accuracy_eval.py` defaults to GPT-OSS-20B and README says any instruction model, but substituting judges changes the protocol and cannot preserve the published 35% comparison. Resolve this before proposing the full lane.

## Novelty audit — scoped claim only

The local complete listing contained **43 OpenRSI Discussions with hasNextPage=false**. No exact FRAMES complete-source-set selector proposal was identified. Adjacent existing ideas must be disclosed:

- [#36 ReasonIR hard-negative curriculum](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/36): retriever post-training via query-difficulty weighting; this fallback must emphasize set complementarity and all-evidence completion rather than curriculum design.
- [#33 Search-R1 rollout/reward redesign](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/33): trains a retrieval-using policy; this fallback freezes the language-model policy and only learns evidence selection.
- [#38 DR Tulu rubric weighting](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/38): long-form research RL; distinct reward/evaluator and artifact.

Relevant research:

- [BridgeRAG, April 2026](https://arxiv.org/abs/2604.03384v2) already conditions relevance on bridge evidence with a training-free tripartite scorer. **Do not claim bridge-aware relevance is new.** The proposed difference is a learned, tightly budgeted set selector, deterministically evaluated on complete-source coverage within the frozen FRAMES corpus.
- [BAR-RAG, February 2026 / ICML 2026](https://arxiv.org/abs/2602.03689) trains a generator-conditioned evidence selector and subsequently trains the generator. Its [official repository](https://github.com/GasolSun36/BAR-RAG) says the selector is discarded at inference. **Do not claim learned evidence selection or using downstream generator feedback is new.** Our narrow question keeps the selector at inference and freezes the generator, if any.
- [LongPAS, Findings ACL July 2026](https://aclanthology.org/2026.findings-acl.1306/) studies process credit assignment for long-context reasoning, including FRAMES. It is adjacent performance evidence, not this task's baseline. The [official repository](https://github.com/GKNL/LongPAS) has training paths but no discovered released trained checkpoints; do not imply all artifacts were released.
- [HiMPO, June 2026](https://arxiv.org/abs/2606.16285) addresses memory-write credit in long-horizon agents, another reason not to market generic evidence/memory retention as unexplored.

The defensible claim is **no identical task found in this repository audit and these nearest primary-source papers**, not “nothing like this exists anywhere.” The mechanism may still prove incremental. D-REX or TurnBench may be stronger for the user's uniqueness preference if their asset issues are resolved.

## Alternatives rejected or deprioritized

- **RLHF_Trust**: [official paper](https://arxiv.org/html/2404.18870v2) reports average truthfulness falling 25%, stereotypical bias increasing 150%, privacy leakage increasing 12% across its tested models/algorithms. The [official source](https://github.com/AI4LIFE-GROUP/RLHF_Trust/tree/ad67ccc359e35009d59af0e8ad0ccb65cf50fb2a) contains evaluator/data/attribution scripts but no paper checkpoints, no pinned environment or LICENSE file in its small tree, and placeholder model paths. Traceable immediate reproduction is weaker. Published evidence concerns up-to-7B historical models, not today's frontier.
- **Iterative prompting truthfulness**: [ICML 2024](https://proceedings.mlr.press/v235/krishna24a.html) establishes degradation and calibration issues. No official runnable repository was located; not a ready artifact choice.
- **AMPLIFY**: [official repository](https://github.com/AI4LIFE-GROUP/amplify) exists, but historic post-hoc rationale methods are already extended by later work. Current poor-performance evidence and a precise modern baseline are weaker than the FRAMES/MLCommons route.
- **ARES**: [ACL July 2026 paper](https://aclanthology.org/2026.acl-long.1985/) is highly relevant and current. The PDF mentions a code release, but no official code URL/public checkpoint delivery was located in this search; do not infer assets exist from that sentence.

# OpenRSI-Index public catalog audit

Audit date: 2026-09-23 (America/Los_Angeles). Read-only public GitHub inspection authenticated exclusively as `y12uc231`. No GitHub mutations and no repository code execution.

## Scope and completeness

- Local source snapshot: [`5d411876624e78b84499e2759b50febbf8cf75a7`](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7).
- All **43 Discussions** fetched: **42 Task Ideas**, one Q&A; 13 closed Discussions included. Discussion pagination says `hasNextPage=false`.
- All **337 top-level Discussion comments and 2 replies** fetched; no comment/reply pagination gaps. Body/current proposal and review status may change after this snapshot.
- All-state REST issue endpoint returned **67 PRs and zero stand-alone issues**; pagination requested through `gh api --paginate`.
- **14 current task.toml task directories**, including 3 signature tasks. README is not a fully reliable current manifest (see caveats).
- Evidence snapshots alongside this report: `discussions.json`, `discussion-comments.json`, `issues-and-prs.json`. These contain public proposal/review text, not executable instructions.

## Findings for selecting an original contribution

The catalog is dense in LLM math post-training (GRPO, PPO, CoT, curricula, distillation, QLoRA), retrieval/agent context, model pretraining/optimizer allocation, visual pointing/GUI interaction, and GPU kernels. Recently added proposals also occupy spatial MLLM geometry fusion (#113), terminal trajectory amplification (#95), CPU online network-resource allocation (#85), and robot insertion reward search (#68). Renaming these broad mechanisms or using a different small Qwen checkpoint would not establish a distinctive task.

No inspected task/proposal has audio/speech, forecasting, learned graph-algorithm extrapolation, tabular distributional robustness/uncertainty, or neural physical-dynamics surrogates as its primary target. These are **catalog gaps**, not proof of global scientific novelty or proof that current frontier models perform poorly. A selected task still needs an auditable upstream baseline, a precise new experimental question, relevant recent prior-art search, and a matched empirical pilot before claiming model failure.

Distinctiveness should be claimed narrowly: “No equivalent proposal found in the audited OpenRSI catalog as of 2026-09-23.” It is impossible to guarantee “not anywhere” from this audit. Unpublished/private task repositories, unindexed work, and later edits are outside its reach.

## Existing task directories

| Task | Primary scope |
| --- | --- |
| [depth-width-allocation](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/depth-width-allocation) | Pretraining: fixed 200M decoder-depth width allocation (related Discussion #13). |
| [learnability-cot](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/learnability-cot) | Post-training: small-model math SFT trace adaptation (#9/#64). |
| [gemm-h100-refined](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/gemm-h100-refined) | MLSys: FP16 CUDA GEMM H100 throughput. |
| [liger-tied-ce](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/liger-tied-ce) | MLSys: tied-weight fused cross-entropy Qwen3 SFT. |
| [minference-sparse-prefill](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/minference-sparse-prefill) | MLSys: Triton sparse attention prefill. |
| [molmo2-pointing-refined](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/molmo2-pointing-refined) | Vision: frozen video-pointing inference strategy (#10). |
| [ace-playbook-repair](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/ace-playbook-repair) | Agent context: intrinsic ACE playbook repair (#14/#25/#32). |
| [molmoweb-interaction-context](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/molmoweb-interaction-context) | Vision agents: frozen MolmoWeb offline context allocation (#12). |
| [reasonir-difficulty-curriculum](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/reasonir-difficulty-curriculum) | Retrieval post-training: difficulty-conditioned negative curriculum (#36). |
| [isaaclab-peginsert-reward-search](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/isaaclab-peginsert-reward-search) | Robotics: fixed-budget PPO reward structure search (#68). |
| [kev-decision-architecture](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/kev-decision-architecture) | Decision-model head/architecture training; knowledge and transfer macro NLL, 0.5B backbone. |
| [signature-tasks/post-training-qwen-122B-rl](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/signature-tasks/post-training-qwen-122B-rl) | Signature post-training: public material currently data-only 0-GPU intervention-contract checker; full 122B training/rec5 scorer absent publicly (PR #89). |
| [signature-tasks/gpic_generation](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/signature-tasks/gpic_generation) | Signature vision generation: PixelGen shared checkpoint on GPIC 10M subset. |
| [signature-tasks/pre-training-optimizer-update-geometry](https://github.com/OpenRSI-Foundation/OpenRSI-Index/tree/5d411876624e78b84499e2759b50febbf8cf75a7/rsi-tasks/signature-tasks/pre-training-optimizer-update-geometry) | Signature pretraining: scale-general optimizer across Marin ladder (#11). |

## Full Discussion inventory

Review status below is the last machine-readable review found in the fetched comment chronology. It is not a claim that the task has been reproduced or publicly included. Closed status does not erase a prior idea from novelty comparison.

| # | Title | State / latest review | Coverage |
| --- | --- | --- | --- |
| [113](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/113) | Making 3D Geometry Matter: Fixed-Budget Fusion in VGGT-Augmented MLLMs | open; Pass | Spatial-MLLM frozen VGGT feature adapter; 3D fusion, matched 3D/2D capacity controls, cross-view geometry intervention diagnostics. Occupies spatial MLLM geometry-use niche. |
| [95](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/95) | Iterative Trajectory-to-Environment Amplification for Terminal Agents | open; Pass | Terminal trajectories → executable environments → generated tasks/rollouts → Qwen agent training; seed-only matched control on Terminal-Bench 2.1/3.0. Occupies environment amplification/self-play niche. |
| [85](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/85) | nfv-resource-allocation | open; Pass | CPU-only deterministic online virtual-network embedding heuristics; revenue under sealed arrival streams. Occupies NFV/resource-allocation heuristic research; not all combinatorial optimization. |
| [79](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/79) | [Workflow E2E Test] Competence-Conditioned Verifiable SFT Self-Play for QUEST-4B | open; Pass | Workflow test duplicate of QUEST #66, not an independent niche. |
| [68](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/68) | Reward Structure Search for Isaac Lab PegInsert under a Fixed Training Budget | open; Pass | Isaac Lab PegInsert reward-graph/phase/weight search under fixed PPO transitions; terminal insertion success. Occupies simulated insertion reward design. |
| [66](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/66) | Competence-Conditioned Verifiable SFT Self-Play for QUEST-4B | open; Pass | QUEST-4B competence-conditioned proposer–solver SFT self-play; fixed BrowseComp-Plus retrieval environment. Adjacent PR #94 specializes single-round curriculum hill climbing. |
| [64](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/64) | 让 Qwen2.5-3B 超越原始 Long CoT 基线 | closed; Pass | Qwen2.5-3B Long CoT improvement across six math benchmarks through training/data/inference changes; broader successor/variant of learnability-CoT #9. |
| [61](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/61) | Coverage-Constrained History-Aware Prompt Sampling for Fixed-Budget GRPO | open; Pass | History-aware/coverage-constrained GRPO prompt allocation to reduce zero-variance groups, fixed rollout budget, math accuracy. |
| [57](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/57) | Consolidating Historical Checkpoint Reasoning into a Single Qwen2.5-7B Model | open; Pass | Distill complementary historical reasoning checkpoints into one Qwen2.5-7B; matched final-only self-distillation control and forgetting diagnostics. |
| [55](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/55) | Bounded Outcome-Conditioned Token Credit for Fixed-Budget GRPO Math Training | open; Pass | Bounded zero-mean outcome-conditioned token credit residual for GRPO math; uniform-credit matched control. |
| [53](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/53) | [Workflow E2E Test] Data-Constrained Pretraining Beyond the Reproduced Baseline | open; Pass | Workflow E2E test duplicate of Slowrun data-constrained pretraining #51. |
| [52](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/52) | [TEST] Data-Constrained Pretraining Beyond the Reproduced Baseline | closed; no parsed marker | Test variant of Slowrun data-constrained pretraining #51. |
| [51](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/51) | Data-Constrained Pretraining Beyond the Reproduced Baseline | open; Pass | Slowrun fixed 100M-token corpus and one-hour 8-H100 run; broad training/data reuse/architecture/optimization method space. |
| [47](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/47) | Frozen-Base MPT-7B-8K to 16K with a Learned Post-Window Query-Temperature Controller | open; Pass | Frozen MPT-7B-8K extension to 16K using learned per-layer/head post-window query-temperature scalars; HotpotQA with general-capability safeguard. |
| [46](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/46) | Informativeness-Gated Target-KL Control for Native Qwen2.5-3B GRPO | open; Pass | Group-informativeness-gated target KL control in Qwen2.5-3B GRPO; GSM8K. |
| [45](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/45) | Data-Constrained Pretraining | closed; Pass | Earlier closed data-constrained Slowrun pretraining proposal; overlaps #51. |
| [44](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/44) | Effective-Context Loss Allocation for Long-Context Qwen2.5 Training | open; Pass | Document-boundary/effective-left-context loss allocation during fixed-budget Qwen2.5 continued pretraining, retrieval/QA evaluation. |
| [40](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/40) | Value-Change Credit Redistribution for LoRA-PPO Mathematical Reasoning | open; Pass | Value-head-change redistribution of terminal math reward across reasoning steps during LoRA PPO; reward-mass preservation. |
| [39](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/39) | Quantization-Residual-Guided Bidirectional Rank Relocation for Fixed-Budget QLoRA | open; Pass | Online QLoRA rank relocation using quantization residuals and task-gradient novelty under fixed rank/parameter budget; GSM8K. |
| [38](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/38) | Reliability-Weighted Evolving Rubrics for Citation-Grounded DR Tulu | open; Pass | Reliability/uncertainty weighting of DR Tulu evolving rubrics for citation-grounded long-form research. |
| [37](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/37) | Learning DCLM Source Mixtures from Early Loss and Gradient Signals | open; Pass | DCLM data-source mixing learned from early per-source loss/gradient signals; fixed 411M pretraining, Core_v2. |
| [36](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/36) | Difficulty-Conditioned Hard-Negative Curricula for ReasonIR Retrieval Post-Training | open; Pass | ReasonIR-8B retrieval LoRA with query-difficulty-conditioned hard-negative curriculum; BRIGHT with general retrieval preservation. |
| [33](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/33) | Training-Time Rollout & Reward Redesign for Budget-Constrained Retrieval QA in Search-R1 | closed; Pass | Closed variant of Search-R1 training-time rollout/reward redesign (#18). |
| [32](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/32) | Intrinsic Quality Inspection and Repair for ACE Playbooks on Formula | open; Pass | ACE Formula intrinsic playbook bullet inspection/repair; fixed model, data, adaptation budget. Variant of #14. |
| [25](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/25) | Intrinsic Quality Inspection and Repair for ACE Playbooks on Formula | closed; Pass | Closed ACE playbook repair variant of #14/#32. |
| [24](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/24) | Budget-Constrained Rollout &amp; Reward Redesign for Retrieval-Augmented QA in Search-R1 | closed; Pass | Closed Search-R1 budgeted rollout/reward variant of #17/#18. |
| [23](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/23) | [TEST] Budget-Constrained Rollout & Reward Redesign for Retrieval-Augmented QA in Search-R1 | closed; Pass | Test Search-R1 variant. |
| [18](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/18) | Budget-Constrained Rollout & Reward Redesign for Retrieval-Augmented QA in Search-R1 | open; Accept | Search-R1 Qwen2.5-3B GRPO training-time query reformulation, summarization, search-stopping and reward shaping under K=4 searches; fixed Judge rollout. |
| [17](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/17) | Budget-Constrained Rollout & Reward Redesign for Retrieval-Augmented QA in Search-R1 | open; Reject | Search-R1 variant allowing candidate inference rollout-driver redesign in addition to training/reward shaping. |
| [16](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/16) | Improving targeted prompt-injection attacks against AgentDojo's fixed defense panel | open; Accept | Targeted prompt-injection strategy search against frozen AgentDojo Qwen3.5-9B across four defense configurations. Occupies attack-side indirect injection research. |
| [15](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/15) | Grounding-Token Mechanism Design for GUI and General Image Pointing | open; require human review | MolmoPoint grounding-token selection-space/geometry/masking mechanism, fixed finetuning; ScreenSpot-Pro and general pointing preservation. |
| [14](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/14) | Intrinsic Quality Inspection and Repair for ACE Playbooks on Formula | open; Strong Accept | ACE Formula intrinsic playbook repair; inaccurate/contradictory/redundant/stale/unsupported bullets. |
| [13](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/13) | Depth-Heterogeneous nanoGPT Architecture Under Matched Compute | open; Accept | Variable-width/nanoGPT depth-heterogeneous 200M architecture allocation under matched parameters/FLOPs/training stream. |
| [12](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/12) | MolmoWeb Interaction-Context Construction for Frozen Structured Action Prediction | open; Accept | MolmoWeb-4B frozen structured-action replay; history text/images/context construction within fixed token budget. |
| [11](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/11) | Optimizer update geometry across a 550M-to-2.545B scaling ladder | closed; Reject | Marin 550M-to-2.545B scale-general optimizer update geometry; multi-scale Paloma/training losses. Published as signature task. |
| [10](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/10) | # Molmo2 pointing refinement | closed; Reject | Molmo2-VideoPoint-4B inference strategy: frame sampling, prompt, generation length on generated-video anomaly pointing; spatiotemporal soft-F1. |
| [9](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/9) | Learnability-aware long/short CoT adaptation | closed; Strong Accept | Small-model long/short CoT learnability through source-response selection/adaptation under fixed full SFT recipe. |
| [8](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/8) | Curriculum Sampling for Cross-Environment Generalization in Simia-RL | open; Accept | Simia-RL APIGen Airline/Retail curriculum sampling for cross-environment OfficeBench generalization; Tau2 preservation. |
| [7](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/7) | 💬 Feedback on Proposal and Harbor Agent Skills | open; no parsed marker | Contributor feedback Q&A, no proposed task. |
| [5](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/5) | TMax-9B Configurable RL Under a Fixed 200-Step Budget | open; Accept | TMax-9B bounded RL objective/update changes under fixed 200 updates for Terminal-Bench 2.0. |
| [4](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/4) | [Test-proposal] Does length-normalized preference optimization reduce verbosity bias? | closed; no parsed marker | Test length-normalized preference optimization versus verbosity bias. |
| [3](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/3) | [TEST-2] Task Proposal - Make some improvements on a binary-parsing library written in Common Lisp | closed; no parsed marker | Rejected Common Lisp binary-parser test proposal; outside model-development research scope. |
| [1](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/1) | [TEST-2] Task Proposal - Make some improvements on a binary-parsing library written in Common Lisp | closed; no parsed marker | Legacy Common Lisp binary-parser test proposal; not evidence of current accepted research scope. |

## Scientific question evidence excerpts

These are exact selected fields from each non-test proposal at the audit time (public text). They are evidence of occupied scope, not independently validated factual claims.

### [113: Making 3D Geometry Matter: Fixed-Budget Fusion in VGGT-Augmented MLLMs](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/113)

Spatial reasoning is essential for navigation, robotic manipulation, and interaction with the physical world: models must understand distances, directions, object relationships, and cross-view changes, not merely recognize visible objects. [VSI-Bench](https://huggingface.co/datasets/nyu-visionx/VSI-Bench/blob/bdcadb3fea447621a828a24911801faba3587c12/README.md) documents the difficulty of these tasks for current multimodal models. [Spatial-MLLM](https://github.com/THU-SI/Spatial-MLLM/blob/9fc47382c7bc5ab52951e6e2e64db08fca0948ee/README.md) adds a VGGT-based spatial encoder alongside a 2D encoder and reports improved spatial QA. Aggregate accuracy alone does not identify how much of a gain comes from useful 3D geometry rather than 2D cues, added capacity, or dataset shortcuts; this is an open question, not an assumption that Spatial-MLLM ignores VGGT.<br>Holding the released checkpoint’s original components, training examples, fixed 16-frame input, and compute budget constant, can a bounded VGGT-to-VLM adapter improve unseen-scene spatial reasoning beyond matched simple-3D and 2D-only controls, with consistent evidence that the gain depends on the geometry branch?

### [95: Iterative Trajectory-to-Environment Amplification for Terminal Agents](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/95)

Under a frozen seed set of at most 1,000 eligible public terminal-agent trajectories and a one-node, 8×H100, 48-hour Work envelope, can an autonomous iterative system reconstruct executable Harbor environments, generate verified tasks and rollouts, revise its internal validation process, and train a Qwen3.8-Flash-Next checkpoint plus executable agent policy that achieves a positive paired improvement over a Judge-produced seed-only control on sealed full Terminal-Bench 2.1 and Terminal-Bench 3.0 evaluations?

### [85: nfv-resource-allocation](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/85)

On a shared 100-node substrate with Poisson arrivals (rate 0.12, 1,000 requests per stream, virtual-network sizes 2–10 nodes), can a deterministic, learning-free heuristic for online virtual-network embedding — accept-or-reject each arriving request immediately and irrevocably, deciding only from arrival-observable information — reach or exceed the published classical heuristic level (node-ranking mapping) and approach a hand-tuned strong human reference, measured by long-term time-averaged revenue on sealed streams disjoint from every stream the agent can see? The question is falsifiable per mechanism: each hypothesis about node ranking, locality-aware placement, fragmentation control, retry/backtracking, or rejection policy either produces a revenue change on the sealed streams distinguishable from stream noise, or the hypothesis is rejected.

### [68: Reward Structure Search for Isaac Lab PegInsert under a Fixed Training Budget](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/68)

Under fixed Isaac Lab PegInsert dynamics, initial-state distribution, PPO configuration, and 3,276,800 training transitions per scored fresh run, can an agent iteratively design reward terms, weights, and phase conditions that produce higher terminal insertion success than a matched original-reward baseline? Judge trains each submitted reward recipe from scratch before measuring success. The aspiration is empirical 100% simulation success under the declared protocol.

### [66: Competence-Conditioned Verifiable SFT Self-Play for QUEST-4B](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/66)

Under a fixed BrowseComp-Plus offline-document environment and matched training and inference budgets, can three rounds of competence-conditioned proposer–solver co-evolution through verifiable LoRA SFT self-play produce a final solver whose avg@3 exceeds that of the unchanged QUEST-4B checkpoint on the Judge-hidden, access-controlled official 130-question QUEST workload, without adding original QUEST training examples, reinforcement learning, or an external training teacher?

### [61: Coverage-Constrained History-Aware Prompt Sampling for Fixed-Budget GRPO](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/61)

Under a fixed total completion-generation budget, can a coverage-constrained, history-aware prompt allocator integrated into TRL’s synchronous GRPO trainer improve held-out math accuracy over the pinned trainer’s seeded shuffled-permutation sampler, while reducing zero-reward-variance prompt groups without collapsing training-prompt coverage?

### [57: Consolidating Historical Checkpoint Reasoning into a Single Qwen2.5-7B Model](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/57)

Can distillation from complementary historical checkpoints improve the single-response MATH-500 accuracy of a model initialized from the released step-256 checkpoint, relative to both the untouched checkpoint and a matched final-checkpoint-only self-distillation control? Measure newly introduced forgetting as a diagnostic, without adding it to the reward.

### [55: Bounded Outcome-Conditioned Token Credit for Fixed-Budget GRPO Math Training](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/55)

At a fixed rollout-token-slot and optimizer-update budget, can a bounded, outcome-conditioned token-credit residual—derived only from the current GRPO rollout group, binary final-answer rewards, and policy statistics already computed in the ordinary training pass—improve held-out mathematical-reasoning accuracy over uniform sequence-level credit? The residual must have zero masked mean within each completion, preserving only its mean advantage; gradient norm, update scale, clipping, and policy KL are measured diagnostics rather than invariants.

### [51: Data-Constrained Pretraining Beyond the Reproduced Baseline](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/51)

Can an automated researcher develop a training method that achieves lower minimum validation loss than a freshly reproduced pinned Slowrun baseline, using the same fixed 100M-token FineWeb training corpus with unrestricted epoching, where each run is limited to one physical 8×H100 node and one hour? Permitted hypotheses include data reuse, curricula and transformations, optimization and regularization, architecture and compute allocation, ensembling, and combinations of these methods.

### [47: Frozen-Base MPT-7B-8K to 16K with a Learned Post-Window Query-Temperature Controller](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/47)

Under the fixed one-node budget and controller-only PG-19 schedule below, does fitting a bounded positional query-temperature controller with one learned scalar per MPT layer/head improve MPT-7B-8K’s protected 16K HotpotQA exact-match accuracy without lowering its protected Eval Gauntlet v0.3 `core_average`?<br><br>For zero-based query position `p`, `u(p)=0` when `p≤8191`; otherwise `u(p)=min(1,(p−8191)/8192)^gamma`. The manipulated query is `q'_(l,h,p)=q_(l,h,p) × exp(u(p) × b × tanh(theta_(l,h)))`. There are exactly 32×32=1,024 learned `theta` scalars, all initialized to zero. Fixed bounds are `0<b≤ln(2)` and `0.5≤gamma≤2`, so every multiplier lies in `[0.5,2]`. An explicit branch returns exact unit scale through position 8191; cached decoding uses `past_position+arange(S)`. All pretrained tensors remain frozen and byte/hash-identical.

### [46: Informativeness-Gated Target-KL Control for Native Qwen2.5-3B GRPO](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/46)

Under a fixed repository-native Qwen2.5-3B synchronous-GRPO protocol, does group-informativeness-gated, observed-target-KL control outperform native fixed `kl_coeff=0.01` in GSM8K mathematical-reasoning accuracy while reducing zero-advantage/KL-only updates or reference-policy-drift instability?

### [44: Effective-Context Loss Allocation for Long-Context Qwen2.5 Training](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/44)

Under a fixed 500-million-token continued-pretraining budget, can a training-only, document-boundary-aware loss-allocation mechanism—which weights token cross-entropy using the usable same-document left context derived from `sequence_id`—improve Qwen2.5-1.5B accuracy on 8K/16K retrieval and question-answering tasks relative to both the released reference checkpoint and an otherwise matched standard-cross-entropy Work control, while keeping general-task accuracy within 1.0 percentage point of the released baseline?

### [40: Value-Change Credit Redistribution for LoRA-PPO Mathematical Reasoning](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/40)

Under the fixed `Qwen/Qwen2.5-Math-1.5B-Instruct` starting checkpoint, fixed deduplicated DAPO-Math-17k corpus, rollout and optimizer-update budget, sampling protocol, and compute lane, which reward-mass-preserving mechanism for redistributing verifiable terminal exact-answer reward across detected reasoning-step boundaries using changes in the PPO value-head estimate yields the highest absolute exact-answer accuracy on the fixed MATH-487 evaluation?

### [39: Quantization-Residual-Guided Bidirectional Rank Relocation for Fixed-Budget QLoRA](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/39)

Under exactly 5,000 successful optimizer updates and 20,000 counted MetaMathQA sample exposures on a frozen 4-bit `Qwen3-4B-Base`, how effectively can a bidirectional policy that relocates paired `q_proj`/`v_proj` LoRA rank using immutable layerwise quantization-reconstruction residuals and online task-gradient novelty maximize deterministic GSM8K exact-match accuracy at an exact fixed budget of 576 total active layer ranks and 5,898,240 trainable adapter parameters, and what do its allocation traces reveal about the interaction between frozen quantization pressure and evolving task demand? Every candidate starts from uniform rank 16; leaving that allocation unchanged is permitted as one normal research candidate, not supplied as a pre-evaluated comparator.

### [38: Reliability-Weighted Evolving Rubrics for Citation-Grounded DR Tulu](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/38)

Within a fixed single-node rollout and search budget, can bounded, criterion-level reliability weighting of DR Tulu’s evolving rubrics—using within-prompt score uncertainty and disagreement between persistent and adaptive rubrics—produce a checkpoint with better citation-grounded long-form research quality than the official released DR Tulu baseline?

### [37: Learning DCLM Source Mixtures from Early Loss and Gradient Signals](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/37)

Under the fixed DCLM 411M-1x architecture, optimizer, token budget, source pool, and matched evaluation suite, can an evidence-driven mapping learned from bounded early per-source loss trajectories and gradient signals produce fixed source weights whose freshly trained model achieves higher Core_v2 than a freshly trained 100% DCLM-Baseline reference?

### [36: Difficulty-Conditioned Hard-Negative Curricula for ReasonIR Retrieval Post-Training](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/36)

Under exactly 1,000 optimizer updates and 64,000 attempted query-positive-negative triplet exposures per candidate, can an offline query-difficulty-conditioned weighting and curriculum policy over the fixed ReasonIR HQ/VL pool produce a fixed-schema LoRA adapter over ReasonIR-8B that improves original-query BRIGHT retrieval while preserving general retrieval? Across at least two completed matched policy trials, do the results support a mechanism-level conclusion about difficulty conditioning rather than extra post-training alone?

### [32: Intrinsic Quality Inspection and Repair for ACE Playbooks on Formula](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/32)

Can a periodic intrinsic playbook inspector that detects and repairs inaccurate, contradictory, redundant, stale, or poorly supported bullets improve mean held-out Formula exact-answer accuracy over stock sequential ACE when both methods use the same fixed local model, data, adaptation budget, and evaluation protocol?

### [18: Budget-Constrained Rollout & Reward Redesign for Retrieval-Augmented QA in Search-R1](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/18)

Under a fixed per-question search-call budget (K=4) and the fixed `nq_hotpotqa` test set, can **training-time** redesign of the multi-turn search rollout (training-time query reformulation, in-context post-retrieval summarization/compression, adaptive search-stopping) **plus training-time reward shaping**, applied via GRPO from Qwen2.5-3B for a fixed 300-step budget, produce a checkpoint that achieves higher EM — evaluated by a fixed rollout harness bundled inside a Judge-only task-owned test — than a standard-recipe Search-R1 baseline trained under the identical 300-step budget? Improvements must be realized as **learned model behavior** expressible within the fixed harness's `<think>/<search>/<information>/<answer>` grammar.

### [17: Budget-Constrained Rollout & Reward Redesign for Retrieval-Augmented QA in Search-R1](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/17)

Under a fixe per-question search-call budget (K=4) and the fixed `nq_hotpotqa` test set, can redesigning the multi-turn search **rollout procedure** (learned query reformulation, post-retrieval summarization/compression, adaptive search-stopping, and trajectory structure via a candidate-submitted rollout driver) **plus training-time reward shaping**, trained by GRPO from Qwen2.5-3B for a fixed 300-step budget, achieve higher EM than a standard-recipe Search-R1 baseline trained under the identical 300-step budget?

### [16: Improving targeted prompt-injection attacks against AgentDojo's fixed defense panel](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/16)

Can an agent discover a targeted indirect prompt-injection strategy that achieves a higher attack success rate than AgentDojo's strongest shipped attack (`important_instructions`) **simultaneously across a fixed panel of four pipeline configurations** (no defense, `tool_filter`, `spotlighting_with_delimiting`, `repeat_user_prompt`) against `Qwen/Qwen3.5-9B` as the frozen victim agent — without degrading the victim's task utility below a declared floor?

### [15: Grounding-Token Mechanism Design for GUI and General Image Pointing](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/15)

Starting from MolmoPoint's grounding-token pointing mechanism, how can the mechanism itself be improved to raise pointing accuracy on dense, small-target GUI screens without degrading general visual pointing?<br><br>The search space is the declared mechanism configuration of `MolmoPointConfig` — the coarse-to-fine `<PATCH>`/`<SUBPATCH>`/`<LOCATION>` parameterization, its selection-space geometry, and its selection-masking policy at training and inference — with the training data, fine-tune budget, optimizer settings, and evaluation protocol all held fixed, so any measured change is attributable to the mechanism alone.<br><br>Success criterion, checkable per candidate: a candidate improves ScreenSpot-Pro `overall` over a matched-budget reference whose mechanism is unmodified, while keeping PixMo-points-eval F1 and the PointBench category mean within the declared eligibility margin. A given mechanism change is refuted when it fails that criterion under the fixed protocol.

### [14: Intrinsic Quality Inspection and Repair for ACE Playbooks on Formula](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/14)

Can a periodic intrinsic playbook inspector that detects and repairs inaccurate, contradictory, redundant, or poorly supported bullets improve mean held-out Formula exact-answer accuracy over stock sequential ACE under fixed model, data, and adaptation budgets?

### [13: Depth-Heterogeneous nanoGPT Architecture Under Matched Compute](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/13)

Under the official 200M dense recipe’s fixed 16-layer depth, 10,003,415,040-token training stream, optimization settings, and source-accounted parameter and training-FLOP ceilings, can a candidate-designed nonuniform allocation of capacity across decoder depth achieve a lower mean late-training next-token loss than the official ><former allocation?

### [12: MolmoWeb Interaction-Context Construction for Frozen Structured Action Prediction](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/12)

With MolmoWeb-4B weights, the action schema, the decoding rule, and the scoring protocol all held fixed, does changing how multi-step interaction context is constructed — which past steps enter the prompt, how each is rendered textually, whether any past screenshots are supplied and at what scale, how page state is expressed, and how the action is serialized — improve structured action prediction on held-out web trajectories?<br><br>The repository default supplies `max_past_steps = 3` textual action summaries and `max_past_images = 0`, i.e. **no past visual context whatsoever**. The falsifiable claim is that this default is not the best use of the available context window.<br><br>The budget is genuinely scarce, which is what makes this a trade-off rather than a free addition. `text_config.max_position_embeddings = 10240` caps the whole sequence, while `preprocessor_config.json` (`378x378` crops, `patch_size 14`, `pooling_size [2,2]`, `max_crops 8`, plus a low-resolution global view) puts one screenshot on the order of one to two thousand tokens. Past visual context and longer textual history compete directly for the same fixed budget, and the default spends all of it on text.

### [11: Optimizer update geometry across a 550M-to-2.545B scaling ladder](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/11)

Across six locked Marin AdamH pretraining scales from 550M to 2.545B parameters, can one mathematically explicit, rung-agnostic optimizer update rule improve both step-matched Paloma micro bits per byte and fixed-window token-normalized training loss, while keeping every rung’s Paloma macro BPB and training-loss regression within 1% of its matched AdamH control? The same equations, parameter-grouping logic, state semantics, and source inventory must apply at E0–E5.

### [8: Curriculum Sampling for Cross-Environment Generalization in Simia-RL](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/8)

With training data strictly limited to APIGen Airline and Retail and the training budget and remaining Simia-RL components held fixed, can changing the curriculum sampling and coverage of those two simulated domains improve pass rates on held-out OfficeBench 2-apps and 3-apps tasks while retaining in-domain Tau² Airline and Retail capability?

### [5: TMax-9B Configurable RL Under a Fixed 200-Step Budget](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/5)

Starting from the same Qwen3.5-9B model, pinned TMax-15K training records, rollout topology, and exactly 200 optimizer updates, can bounded changes to the RL objective and update mechanics improve mean Terminal-Bench 2.0 programmatic-verifier reward relative to the official TMax-9B step-200 DPPO checkpoint?

## Catalog and evidence limitations

- README lists `datacomp-small-filtering`, but its task directory was deleted by [PR #91](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/91). The historical niche (DataComp-small filtering for CLIP-like training) remains previously occupied. [PR #86](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/86) separately removed DataComp and depth-width logs, not initially the tasks.
- `paged-gqa-decode` was introduced by [PR #20](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/20), but is absent from the current task directories. Treat GPU attention decode as historical coverage.
- README advertises Qwen-122B-RL with 256 H100s, while [PR #89](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/89) states the public task checks a fixed 2,560-record data intervention contract on 0 GPUs; full t40 training/rec5 scoring is absent from the public release. Public executable completeness must not be inferred from the task title.
- [PR #94](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/94) adds another QUEST proposal (Luna single-evaluation hill climbing), so Discussion search alone misses relevant proposal variants.
- Repo-reported and paper-reported model numbers in most Discussions are explicitly unreproduced under their exact new protocols. This catalog therefore does **not** establish that frontier research agents fail those tasks or a new proposed task.
- Concrete benchmark difficulty example already occupied: [Kev PR #99](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/99) reports untouched decision-model reward 0.25186 versus uniform 0.2488 and Codex best 0.29233. [PR #101](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/101) supersedes the original Claude result after excluding a base-model answer-scoring bypass; corrected Claude best is 0.28955. Do not reuse withdrawn 0.30518 as current evidence.

## Proposal design lessons visible in reviews

- [#113](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/113) initially failed because a fixed 300-question media-valid workload had no demonstrated eligible count or explicit shortfall fallback. It later passed after concrete validity/cardinality work. Either verify counts now or define deterministic eligibility and fallback semantics.
- [#95](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/95) initially failed because the matched-control training script was unavailable in the cited source; source, baseline, and readiness gates all failed. An upstream README or paper alone is insufficient when the actual comparator relies on missing code.
- [#55](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/55) shows multiple revisions: identity/expertise disambiguation, honest shared-snapshot integrity boundaries, and exact dataset filtering/order matter. Final-passing text avoids claiming unsupported clean-Base isolation.
- Current review practice distinguishes unchanged released reference artifacts from Work-produced matched controls; it expects direct-candidate or evaluator-owned-training mode to be explicit, along with unscored invalid/incomplete/infrastructure-failure semantics.
- Latest proposals declare one physical node and at most 8 peak GPUs; sequential Work/Judge consumption should not be added as simultaneous peak. Runtime estimates and ability to complete iterative loops must be described as unmeasured until a pilot.

## Full PR inventory

All 67 returned records are closed PRs; no ordinary issues were returned. Titles below are source titles.

| PR | Title |
| --- | --- |
| [122](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/122) | docs: align contributors with the team page |
| [121](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/121) | Update README to include RSI Logs Viewer link |
| [120](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/120) | Update README.md |
| [119](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/119) | Codex/rsi logs dashboard |
| [118](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/118) | feat(harness): add Slurm cluster support |
| [117](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/117) | Remove Twitter badge from README |
| [116](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/116) | Update README.md |
| [115](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/115) | Update README.md |
| [114](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/114) | docs: restore project README on repository homepage |
| [111](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/111) | Use proxy-backed Luna high for rubric review and share proxy with PR trials |
| [110](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/110) | Fix queued-before-building order for Discussion tasks |
| [109](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/109) | Restore GPT-5.6 Terra medium for proposal rubric review |
| [108](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/108) | Retry transient rubric API failures with exponential backoff |
| [106](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/106) | Use GPT-6 Luna high for proposal rubric review |
| [105](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/105) | docs: align GPIC task description with logged 10M settings |
| [104](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/104) | Add Kaiyuan Zheng to organizers |
| [103](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/103) | add sanitized optimizer task environment |
| [102](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/102) | Move GPIC research trajectories under signature tasks |
| [101](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/101) | Kev decision-architecture: decision-head rule and Claude rerun |
| [100](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/100) | Add GPIC 10M autoresearch trajectories |
| [99](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/99) | Publish Kev decision-architecture task and paired 12 h run archives |
| [98](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/98) | Delete .agents/skills/redact-release-artifacts directory |
| [97](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/97) | docs: update website link and WeChat group image |
| [96](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/96) | Docs/contributors layout links |
| [94](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/94) | Add Luna single-evaluation hill-climbing proposal |
| [93](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/93) | docs: match Contributors layout and add member links |
| [92](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/92) | docs: archive Qwen-122B-RL Formal v8 research visualization |
| [91](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/91) | Delete rsi-tasks/datacomp-small-filtering directory |
| [90](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/90) | Add portable optimizer geometry task, data setup, and sanitized trajectories |
| [89](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/89) | Add Qwen3.5 synthetic RL data Harbor task |
| [88](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/88) | Publish Isaac Lab PegInsert reward-search task and paired run archives |
| [87](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/87) | Sync proposal research-loop budget guidance |
| [86](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/86) | rsi-logs: remove datacomp-small-filtering and depth-width-allocation archives |
| [84](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/84) | Publish learnability-cot Codex run (7.7 h budget), replacing the short recording |
| [83](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/83) | fix(harness): raise the Docker API read timeout above a large rootfs commit |
| [82](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/82) | Publish ACE, MolmoWeb, and ReasonIR lightweight tasks and run logs |
| [81](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/81) | fix(harness): let an accepted Judge round finish when the Agent times out |
| [80](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/80) | fix: support Python 3.9 in proposal submission helper |
| [77](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/77) | fix: clean obsolete checks and resolve Harness completion race |
| [76](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/76) | docs: add Call for Compute below Call for Contributors |
| [75](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/75) | Fix README centering, badge spacing, and title lettering |
| [74](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/74) | Rename project to OpenRSI Index and update repository references and workflows |
| [73](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/73) | fix(harness): feed the Claude Code prompt on stdin instead of argv |
| [72](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/72) | fix(harness): resolve pinned agent hosts without external DNS |
| [71](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/71) | fix(harness): attest concurrent per-bridge firewall policies |
| [70](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/70) | Update README.md |
| [69](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/69) | Enhance contributor section with co-authorship details |
| [67](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/67) | Recover Discussion workflows after transient GitHub failures |
| [65](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/65) | fix: post Discussion queue notices after task dispatch |
| [63](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/63) | docs: clarify proposal-agent onboarding and chat prompts |
| [62](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/62) | Fix rubric repository evidence parsing for proposal tables |
| [60](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/60) | Support CPU-only proposals and local task execution |
| [59](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/59) | Remove proposal-session hooks and simplify onboarding |
| [58](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/58) | Fix stale protected-file hashes for GEMM and Molmo2 |
| [56](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/56) | Clarify shared-runtime proposal review boundary |
| [54](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/54) | Sanitize personal and deployment details in public tasks and logs |
| [50](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/50) | logs: add Claude Opus 5 run for minference-sparse-prefill |
| [49](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/49) | logs: add Claude Opus 5 run for liger-tied-ce |
| [48](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/48) | logs: add Claude Opus 5 run for gemm-h100-refined |
| [35](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/35) | Backup/main before filter repo 2 d03aaf25 |
| [34](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/34) | Backup/main before filter repo 097e9c44 |
| [22](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/22) | Add minference-sparse-prefill task and one validated run log |
| [21](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/21) | Add liger-tied-ce task and one validated run log |
| [20](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/20) | Add paged-gqa-decode task and one validated run log |
| [19](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/19) | Add gemm-h100-refined task and one validated run log |
| [6](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/6) | chore: remove apps/proposal_agent |
| [2](https://github.com/OpenRSI-Foundation/OpenRSI-Index/pull/2) | Define AutoResearch proposal review rubric |

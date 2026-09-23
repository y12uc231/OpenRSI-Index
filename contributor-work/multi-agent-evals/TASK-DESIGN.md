# Candidate task: adaptive joint verification for multi-agent coding

Status: recommended research direction, pending a matched implementation pilot. This is a task design, not the official proposal or a globally new benchmark claim.

## The actual challenge

Two frozen coding workers implement different features in the same repository. Their changes may interact through APIs, state, configuration, and assumptions. A reusable coordination policy must decide when to exchange evidence, when to combine work and run joint checks, and how to allocate the remaining budget to repair. The final evaluator requires both features to work together.

The OpenRSI research agent receives the existing team scaffold, public development tasks, and diagnostics. It must improve the coordination policy through repeated experiments. It submits that policy, not hand-solved patches for individual evaluation tasks. A fresh inner team runs the submitted policy on held-out tasks.

**Scientific question:** Does selecting integration checks from evidence of changing cross-agent dependencies improve held-out joint feature completion under a fixed total budget, beyond a strong generic team and unconditional verification?

A falsifying result is equally useful: adaptive verification provides no improvement after matching total inference/execution cost, or its gains disappear on new repositories.

## Why this is a stronger candidate

[CooperBench](https://github.com/cooperbench/CooperBench/tree/63b9d44d9f39a02fccf5bf0052db48a917a011fd) already supplies real repositories, independently described features, exact tests, agent-team orchestration, and fresh evaluation containers. The 50-pair flash subset covers 20 base tasks in 11 repositories. It is suitable for infrastructure screening, with the explicit caveat that it is public and overlapping pairs share features.

The latest official [team trajectories](https://huggingface.co/datasets/CooperBench/team-trajectories) report 403/651 (61.9%) without a typed communication protocol and 390/636 (61.3%) with it. These are not matched denominators, and they are not our measurements. They make the required baseline clear: we should beat a competent existing team, not assume that adding message structure is new or sufficient.

The potential contribution is **adaptive allocation of joint verification and repair with cross-repository transfer**. Contract-first, plan-first, late-sync and question-first protocols already exist upstream. Multi-agent code integration also already exists. The audited OpenRSI catalog has no equivalent task, but absence from that catalog is a narrower claim than world-first novelty.

## Controlled experimental design

| Component | Contract |
| --- | --- |
| Inner team | Two fixed worker models, plus the same allowed coordination interface in every team condition. Any coordinator/model helper inference counts in the budget. |
| Research artifact | Versioned policy code, prompts, compact shared-state schema, and optional development-trained risk estimator. |
| Editable decisions | Dependency-evidence requests, context selection, sync timing, joint-check selection, repair routing, and stopping. Structured tools and full recomputation are allowed. |
| Fixed assets | Worker checkpoint or explicitly recorded service version, task/base commits, image digests, feature requirements, merger, tests, evaluation manifest, and budget accounting. |
| Primary score | Fraction of prescribed held-out pairs where both feature suites pass. Report absolute score and paired improvement over the fixed reference. |
| Essential controls | Current team without typed protocol; fixed contract-first team; unconditional joint verification; equal-budget solo. |
| Diagnostic scores | One-feature completion, semantic failures after clean merges, merge failures, repair recovery, inference usage, tool/verification calls, latency and infrastructure failures. |
| Generalization | Group by repository or base task before splitting; no shared feature/base PR across development and evaluation. Exact manifest must be frozen after infrastructure eligibility checks and before policy tuning. |
| Failure accounting | Wrong completed solutions fail normally. Malformed candidate policy, timeout, infrastructure or incomplete executions are separately identified and unscored in OpenRSI unless an explicit finite failure rule is adopted. No favorable-denominator filtering. |

The fixed aggregate inference budget must include all workers, coordinator calls, retransmitted context, failed calls and retries; per-agent dollar defaults are not enough. Local open-weight serving and hosted APIs need distinct budget definitions. Choose the operational budget from an infrastructure pilot, then freeze it before policy comparison. A budget curve is preferable to one arbitrarily tight cap.

The task does not award correctness for a self-reported completion message or verifier attestation. The trusted evaluator runs the submitted changes. The existing patch-merging/fallback policy must be preserved for comparable controls or explicitly replaced for every condition.

## Feasible execution plan

1. Pin the source above and image digests. Audit a small fixed feasibility manifest before looking at model outcomes. Run untouched-base and combined-oracle checks to distinguish broken fixtures from model failure.
2. Validate the current strongest team policy and telemetry on that exact manifest. Include all prescribed pairs in the accounting. This supplies actual runtime, memory, token usage and baseline accuracy.
3. Produce a protected OpenRSI wrapper: judge-owned test/reference assets, controlled inference access, fresh score outputs, and aggregate budget enforcement. The original Docker runner is useful but not a complete hostile-candidate boundary.
4. Run the outer researcher on development repositories. Candidate changes must operate across task IDs and may not retrieve gold patches. Evaluate the final policy on frozen held-out repositories.
5. Only then conclude whether the task offers difficult, repeatable research headroom. A cheap general solution reaching the ceiling is evidence to retire or redesign the task.

A likely reproducible worker option is the publicly released Qwen3-Coder-30B-A3B-Instruct used in the older CooperBench study. Its historical 13.3% cooperative score is motivation only; current team code may perform differently. No GPU fit, throughput or current baseline is claimed without measurement. The local Codex pilot in this contribution uses the user's existing runner; it does not establish a portable OpenRSI inference service.

## Submission readiness

The [source audit](COOPERBENCH-SOURCE-AUDIT.md) contains exact implementation paths, launch interfaces and limitations. Missing task-defining choices are worker access/hardware, concrete aggregate budget, protected evaluator adaptation and the grouped evaluation manifest. Contributor publication name/email also remain to be supplied. Runtime is **Estimate incomplete**.

OpenRSI proposals precede full baseline reproduction; a reproduced score is not mandatory merely to draft. However, the source, baseline, evaluation contract and usable access path must be concrete. We will use the [official Section / Field / Proposal template](https://github.com/OpenRSI-Foundation/OpenRSI-Index/blob/5d411876624e78b84499e2759b50febbf8cf75a7/.agents/skills/proposal-agent/references/proposal-template.md) when those defining choices are settled. No formal proposal or upstream Discussion has been submitted for this candidate.

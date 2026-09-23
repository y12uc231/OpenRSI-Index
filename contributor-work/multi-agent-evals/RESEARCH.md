# Multi-agent OpenRSI contribution: research and executable screening

Research date: 2026-09-23. This is a design and evidence report, not an accepted OpenRSI proposal or a claim that a new benchmark is globally unique. All authenticated GitHub publication for this work uses the contributor's personal account, `y12uc231`.

## What we are trying to evaluate

There are two nested evaluations. In the inner evaluation, several frozen model agents must cooperate on an objectively graded task. In OpenRSI, an outer research agent changes the coordination method, runs experiments, and tries to improve the inner team's held-out score under a fixed total budget. Weak worker-model performance does not prove that improving their scaffold is a hard research problem.

The strongest practical research direction is **learning when a team needs to synchronize and verify joint work**. The candidate deliverable is a portable coordination policy: dependency-aware handoffs, evidence summaries, selective verification, and repair scheduling. The workers, repository tasks, task permissions, grader, and aggregate resource budget stay fixed. This is inference-method research; it does not require training an entire foundation model.

## Published evidence, with the correct denominators

These are external reported results, not measurements from our prototype, and they are not directly comparable across rows.

| Source | Reported result | What it does and does not establish |
| --- | --- | --- |
| [Silo-Bench, Table 2](https://arxiv.org/html/2603.01045v1) | GPT-OSS-120B: 22.0% distributed versus 73.3% centralized on five-agent Level III | The score averages individual-agent correctness; it is not the fraction of fully solved team episodes. Static arithmetic tasks may be solved with code. |
| [Alem, Table 1](https://arxiv.org/html/2606.08340v1) | Hard coordination: GPT-5.4-high 4.2%; Gemini-3.1-pro-high 17.5% | Percent of maximum coordination reward, not task success. Strong difficulty signal; the full study is expensive, with long episodes and many model calls. |
| [TeamBench project](https://teambench.github.io/) | Full-team results include Opus 4.7 37.8%, GPT-5.4 27.8%, Gemini 3.1 Pro 28.9% | Main leaderboard uses 90 tasks and one model call per role; only 57 tasks are in the audited verified subset. These are not unrestricted-agent ceilings. |
| [CooperBench older leaderboard](https://cooperbench.com/leaderboard) | GPT-5/OpenHands 27.95% cooperative vs 48.31% solo; Qwen3-Coder-30B/OpenHands 13.3% vs 21.6% | Both-feature completion on real repositories. Older model/harness combinations, not current frontier results. |
| [CooperBench newer team trajectories](https://huggingface.co/datasets/CooperBench/team-trajectories) | GPT-5.5/Codex: team 390/636 (61.3%); solo 362/652 (55.5%); team without typed protocol 403/651 (61.9%) | Scaffolding can improve teamwork substantially. Denominators differ; do not treat these as a strictly paired comparison or claim all current models score around 25%. |
| [BulkPR-Bench](https://arxiv.org/abs/2608.02685) | 8/324 runs complete the entire PR queue exactly | Strong integration difficulty, but this is not itself a teammate benchmark; its whole-queue score is a conjunction of many requirements. |

## Novelty audit

Existing work already covers most broad pitches: [CooperBench](https://arxiv.org/abs/2601.13295) for conflicting code changes, [TeamBench](https://teambench.github.io/) for asymmetric roles, [MAAR](https://arxiv.org/abs/2603.29632) for multi-agent ML optimization, and [BulkPR-Bench](https://arxiv.org/abs/2608.02685) for interacting PR integration. [CoLLAB](https://agents-collab.github.io/) covers distributed constraints. Calling any of these generic ideas new would be misleading.

The temporal direction also has close precedents: [ClawArena](https://arxiv.org/abs/2604.04202) changes staged evidence; [STALE](https://arxiv.org/abs/2605.06527) tests downstream adaptation after belief revision; [CommitGuard](https://arxiv.org/abs/2607.10487) covers invalidation, provenance, stale callbacks, and commit-time checks. A possible narrower contribution is **positive recovery of the best joint plan while retaining independent valid supports**, not merely detecting stale information. That remains a candidate distinction, not a proven global novelty claim.

The OpenRSI catalog audit covered all 42 Task Ideas among 43 Discussions, 337 top-level comments plus two replies, 67 PRs, and 14 current task directories at upstream commit `5d411876624e78b84499e2759b50febbf8cf75a7`. No primary task for runtime coordination over private evidence and live plan revision was found. However, [ACE playbook repair](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/14) already repairs stale and contradictory shared memory. The defensible distinction is distributed runtime decisions and joint outcomes, not memory repair in general.

## Original diagnostic we built: RelayRepair

[Runnable prototype](../relayrepair/prototype/README.md) and [preregistered pilot protocol](../relayrepair/pilot/PROTOCOL.md).

Three workers hold different evidence and dependency rules; a coordinator selects the highest-utility feasible experiment plan. An authoritative source changes. The team must stop relying on superseded evidence, retain conclusions with surviving independent support, and select the correct plan despite delayed older reports. All source revisions are observable. An always-feasible fallback prevents impossible episodes; the main score is one final plan decision, not a product of numerous grading conditions.

The CPU-only Python prototype includes a seeded generator, model-facing observations, an independent structured oracle, a visible-text symbolic parser, exact scoring, and six unit tests. Twelve cases were fixed before substantive model inference: four decision-changing updates, four preserved alternative supports, and four irrelevant updates. Names, counts, utilities, and role ownership vary. The graph skeleton is deliberately small and fixed.

Measured scripted controls:

| Program | Final ordered evidence | Final evidence with delayed old cards |
| --- | ---: | ---: |
| Highest source revision + exact dependency evaluation | 12/12 | 12/12 |
| Latest-arriving report wins | 12/12 | 8/12 |
| Keep the initial plan | 8/12 | 8/12 |
| Abstain | 0/12 | 0/12 |

**These are program scores, not LLM scores.** The six tests pass. The strong symbolic program establishes solvability and demonstrates that this structured version has little research headroom. It would be a mistake to forbid that program merely to make models look worse.

The completed [model smoke test](../relayrepair/pilot/RESULTS.md) scored 12/12 for both the team and the centralized control, confirming this version is too easy for the intended contribution. It requests the existing local Codex configuration, `gpt-6-astra` / `ultra`, with separate tool-free calls and explicitly passed messages. Twelve cases share each role's context, so they are not twelve independent trials. There are nine planned calls: three workers and a leader in each of two rounds, plus a centralized final control. This cannot establish poor performance for most models.

## Three ambitious directions, ranked by purpose

1. **Practical OpenRSI contribution: improve coordination on executable repository tasks.** Use an existing source-pinned harness and strong team baseline. Research dependency-aware handoffs, selective joint verification, repair allocation, and communication efficiency. Test held-out repositories at a matched aggregate token/tool/compute budget. Ordinary code, structured ledgers, and full recomputation remain allowed. The contribution is the research task and transferable improvement, not a claim to invent repository teamwork.
2. **Original benchmark development: distributed evidence recovery.** Expand RelayRepair only if heterogeneous evidence acquisition and relevance selection remain challenging after a strong extract-and-solve baseline. Hold out dependency structures and document families, include outcome-preserving updates, and prove that sufficient information fits the communication budget. The current toy is not enough.
3. **Longer-term research track: reproducible joint ML improvement.** Agents change interacting model/data/optimizer components; measured gains must survive integration, corrected experiment provenance, and fresh seeds. This is closer to scientific research but requires actual training workloads and overlaps MAAR. It is more work than the quickest executable coordination study.

## Research contract for the practical direction

Scientific hypothesis: a policy that requests targeted dependency evidence and verifies affected interfaces can improve joint task completion more efficiently than uniform repeated discussion or unconditional verification. The null is that a competent generic team with the same aggregate budget performs just as well, or that improvement fails to transfer to unseen repositories.

The outer researcher may edit message construction, evidence representations, scheduling, retrieval of shared work state, and verification/repair allocation. It may use development rollouts to fit a small policy. It may not change worker models, task permissions, feature requirements, hidden tests, evaluation seeds, the scored task set, or budget accounting. A completed materialized policy is evaluated directly; the judge does not silently train a new one.

Primary metric: fraction of task pairs with both requested features passing the trusted evaluator. Report individual-feature completion, regressions, communication/inference usage, tool calls, and infrastructure failures separately. Compare a current competent lead/member baseline, a solo control, and relevant policy ablations under the same budget. Do not multiply unrelated requirements solely to lower the headline score.

Use development tasks for policy iteration and repository-grouped held-out tasks for evaluation; exact split counts require an audited manifest. Public upstream tasks leave a contamination risk even when tests are judge-owned. OpenRSI's shared Work/Judge snapshot requires protected judge assets and fresh trusted grading; it is not an independently clean environment. A protocol that simply centralizes information or writes a symbolic tool must be allowed to win.

## Before an exact-template submission

A source audit and toy smoke test are not enough to claim that this is a validated difficult OpenRSI task. Required defining choices: a pinned trustworthy execution path, a strong matched reference policy, declared model access and aggregate budget, and a usable held-out manifest. An outer improvement pilot is additionally needed to support the requested difficulty claim; full baseline reproduction is not a general prerequisite for an OpenRSI proposal. Publication name/email must come from the contributor. Runtime estimates should be labeled estimates until reproduced.

The user selected local Codex for the initial pilot and preparation of other model runs. No paid API model runs are authorized by that choice. No upstream Discussion or PR has been submitted for this work. The exact official proposal table should be completed around the final validated task, rather than filled with invented baseline, compute, or access claims.

# Research contract for proposal review

Working title: **JointVerify: Learning When Cooperating Coding Agents Should Test and Repair Together**.

## Falsifiable question

Can an outer research agent learn a reusable policy for allocating a fixed two-worker budget between implementation, public executable integration checks and targeted repair that improves both-feature completion on repositories outside policy development, compared with competent fixed schedules and serialization?

The intervention is the allocation policy. Worker model, context management, feature specifications, tools, token caps, integration semantics and final tests remain fixed. Failed public checks provide development supervision for a risk estimator or decision policy. The research loop is change or fit policy → run development episodes → observe failures/costs → update policy → submit the materialized policy to Judge. A winning method could be a learned risk predictor, a symbolic rule or a hybrid. Hand-authoring benchmark fixes is outside the action space.

## Reference and controls

The source is CooperBench at `63b9d44d9f39a02fccf5bf0052db48a917a011fd`, with 652 feature pairs from 30 base tasks across 12 repositories. Upstream published team results are not scores for our chosen model or budget. Its no-typed-protocol team retains planning, shared scratchpad, task lists, refresh and integration/repair tools; removing those would create an artificially weak baseline.

Use the fixed periodic verification policy as the traceable reference artifact under this task's adapter. Preserve competent lead/member instructions and ordinary code editing, testing, patch inspection, messaging and repair. Include unconditional verification, always-serial member-then-lead integration, and centralized implementation of both specifications as matched controls. An official-team result must be labeled an adapted baseline unless the full upstream harness/configuration is faithfully run. The local implementation contains three verification policies plus serial and centralized controls. Their model comparison and a faithful official-team baseline remain work before scientific claims.

Solution materializes the baseline policy/configuration and pinned model references; it does not train or evaluate. Judge scores one candidate at a time. The baseline is measured separately under the same contract, not regenerated inside every candidate evaluation.

## Study inputs and split

Keep both repositories already inspected by the local feasibility pilot in development. Select six further development repositories and four evaluation repositories with a fixed public hash rule. Select up to three pairs per repository, balancing distinct base tasks first. This yields up to 24 development and 12 evaluation pairs. The generated manifest records every identity, rule and source hash before policy outcomes; source availability is separate from executable fixture validation.

All exclusions must concern infrastructure or missing assets, never model success. Any required replacement is deterministic within the same repository. If a repository has fewer than three valid pairs, use all valid pairs and disclose the denominator. If it has none, the study contract must be revised and refrozen before comparison. Final score averages the four repository pass fractions, rather than weighting repositories by their pair count. Twelve evaluation pairs are a coarse iterative signal, not adequate evidence for a broad leaderboard claim.

## Reproducible worker and budget

Proposed worker: Qwen3-Coder-30B-A3B-Instruct revision `b2cff646eb4bb1d68355c01b18ae02e7cf42d120`, BF16, two logical workers sharing one vLLM server. The prepared runtime, tokenizer and weight artifact manifest are in `compute/`. No model replacement based on poor scores is allowed. GPU fit and throughput remain unmeasured.

The prepared endpoint pilot uses one million aggregate input-plus-output tokens per pair, at most 200 requests and 4,096 output tokens per request within a 32,768-token context. Retransmitted/cached context, every helper call, retries and replacement generations count. Requests require exact tokenizer preflight plus an enforceable output cap. No free external LLM judge or coordinator is allowed. Capacity calibration occurs before condition comparison; if normal coding cannot fit, record and revise the contract once for all arms rather than claiming a coordination failure.

Proposed executable-work budget is 1,800 aggregate tool wall-seconds per pair, four automatic public joint checks, and a 3,600-second work deadline. Every worker shell command, including worker-initiated tests, consumes the same tool-time pool. This is elapsed tool time, not process CPU time. Pin per-command CPU/RAM/process limits equally across arms. Public checking includes integration/launch overhead. Final protected grading runs once after work stops and has a separate evaluator timeout; record its cost but do not let an empty remaining work budget bypass grading.

The local Codex feasibility pilot has a separate preregistered 32-call/900-tool-second contract. It is not evidence that the endpoint budgets are sufficient or token matched. Do not pool the two lanes.

## Deliverable and boundaries

The candidate is an executable policy package, with configuration and optionally development-trained parameters, that chooses the next worker, a joint-check checkpoint, a repair target and stopping from allowlisted public state. The tested intervention is scheduling and selection of existing feedback, not arbitrary rewriting of worker instructions. Prompts, feedback rendering and context management are fixed. Work may edit that policy package, fit parameters on declared development episodes and use symbolic analysis of visible source/patches. Public tests may be generated only through the same charged worker actions available in every condition; the policy itself cannot inject free-form commands or instructions. The initial check action runs the fixed public targets plus tests created by workers; selecting arbitrary test subsets is a future separately declared condition, not an implied v1 capability. Work must not alter the frozen worker, budget proxy, split, reference answers, test injection, scoring code or task specification; no per-evaluation-case hard-coded patches.

Web search and external inference services are disabled during Work/Judge. Public artifacts are downloaded by task setup using immutable URLs before experiments. Outer Work receives sanitized development repositories and feature descriptions, not a complete upstream checkout, reference patches, protected feature tests or a Judge asset archive. The candidate policy callback receives only serialized allowlisted public state and runs without evaluator asset mounts; its output is validated against the declared action schema. The current local pilot controller intentionally has a complete source checkout for final grading, while its inner workers are isolated; this alone does not implement the proposed outer-Work packaging boundary. Workers have no network, host mounts or credentials. The trusted controller alone accesses the pinned model server on host loopback. Additional data is limited to source analysis, generated public tests and trajectories from the declared development workloads; no external dataset collection or evaluation-test mining.

## Score and failure behavior

Primary score is the mean across evaluation repositories of the fraction of feature pairs for which both protected feature suites pass, from 0 to 1, higher is better. A finite failed solution scores zero for that pair when the resulting artifact fails the protected suites: missing feature, attributable compilation/import error, illegal memory access, candidate executable crash or ordinary failing tests. A merge conflict invokes the fixed lead-only fallback and that resulting artifact is graded normally; a raw conflict does not itself force a zero. Normal worker-budget exhaustion always submits the current patches to Judge and may still earn a pass. Exhaustion itself is not a failure scalar.

An invalid policy package or orchestration crash that prevents the defined evaluation, infrastructure failure, absent required usage telemetry, or whole-evaluation timeout is unscored. Never remove such cases and report a favorable reduced-denominator accuracy. One infrastructure retry may repeat the same pair, seed and unchanged candidate after the cause is repaired; its attempts and costs are disclosed. A policy-code fix is a new submitted candidate. Worker transport failures are incomplete outcomes, not evidence of model reasoning failure.

Return aggregate score, aggregate feature/merge/check-cost diagnostics and bounded operational errors to the outer agent. Development trajectories and public test feedback are fully available. Evaluation feature-test content, expected answers, reference patches, per-case Judge traces and evaluator internals are not returned by default. Public source data makes perfect secrecy impossible; the task must enforce access boundaries and disclose prior-exposure risk.

The shared OpenRSI Base/Work/Judge snapshot is the actual trust model: Judge reloads the materialized Work candidate and injects task-owned tests Judge-only. It is not an independent clean-Base Judge. The adapter's fresh inner containers and allowlisted patches reduce accidental interference, but candidate Python executes inside pytest. These controls do not prove adversarial grader security. Repeated aggregate feedback also permits adaptive overfitting; repository transfer is not a promise of an untouched secret test set.

## Noise, cost and decision rules

Fix worker sampling settings and seeds across paired baseline/candidate runs. Record stochastic output and serving metadata. After measuring baseline variability, repeat only when variation could change the conclusion; analyze pairs grouped by base task/repository. A one-pair gain out of 12 is exploratory, especially after many adaptive submissions. Do not invent significance or a universal minimum improvement before measuring variance.

Proposed peak: one physical node, one H100 80GB, 16 CPU cores, 64–128GB host RAM. Policy editing is CPU-only; development episodes and Judge worker inference use the same GPU. Work pauses for Judge. Eight GPU-hours are requested for initial capacity/baseline validation, not promised to cover a complete contribution. Full outer research budget defaults to 24 hours, extendable to 48. Per-candidate Work, Judge and combined runtime are **Estimate incomplete** until measured; therefore complete loops per 48 hours are also unknown. A measured cycle over 4.8 hours would trigger the workflow's non-blocking compute flag and an explicit scope decision.

Proceed if there are successful individual implementations plus repairable interaction failures. If both centralized and team policies are at floor, first assess competence and budget. If strong controls are near ceiling, report that and study cost at fixed correctness or enlarge independently chosen coverage. Do not manufacture a low score by weakening the model, withholding normal tools, selecting failures after the fact, or tightening a successful baseline's budget.

## Submission status

The code/evidence packet can support an exact-format OpenRSI proposal. Public identity and relevant expertise are verified in `AUTHOR-EVIDENCE.md`. The contributor controls publication contact details; hardware access and final review remain pending. The proposal must preserve the official 28-row Section / Field / Proposal table when these details are resolved. GPU measurements and full benchmark implementation are explicitly labeled work for validation, not fabricated proposal evidence. Do not submit with invented author information.

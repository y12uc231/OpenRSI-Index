# JointVerify: frozen local feasibility pilot

Preregistered on 2026-09-23, before any JointVerify model episode. This is a local orchestration feasibility pilot, not a reproduced CooperBench leaderboard or a matched-token cross-model study.

## Sample and assets

Use the three pairs in `manifests/pilot-v1.json`: `click2068_1_6`, `click2800_1_3`, and `dirty43_2_3`. These were selected for CPU-light Python execution before observing model outcomes. They are not a representative population sample. Source revision, feature specifications, hidden test patches, combined reference patches, original base commits, and container image digests are pinned in the manifest. Evaluator calibration verifies that all three combined references pass both feature suites, all three untouched bases fail both, and all three independently combined single-feature references fail integration. Those are infrastructure controls, not model scores.

## Workers and budgets

Use the existing local Codex configuration, `gpt-6-astra` with `ultra` reasoning. Each call is independent and tool-free, returning a structured JSON command, message, or completion. The controller executes commands in two private network-disabled Docker workspaces, with no host credentials or mounts and with later Git history removed. The lead receives both feature descriptions and explicit integration responsibility; the member implements its assigned feature. Both see exchanged messages and the peer patch snapshot.

Per episode, allow 32 aggregate model calls, four public joint checks, 900 aggregate tool wall-seconds, and a 3,600-second work deadline. Each worker command is limited to 90 seconds; each model call is limited to 480 seconds or the remaining episode deadline. The mandatory final Judge is outside the work budget. Record all model input and output tokens, including retransmitted context and inclusive reasoning output. The CLI does not expose the hard per-call output cap needed for guaranteed token reservations: these results are call-count constrained, **not token matched**. No API or paid model endpoint is used.

Fixed conditions are periodic checking after two worker turns, unconditional checking whenever a changed joint candidate is available, and a dependency heuristic with a four-turn fallback. The heuristic uses changed paths and regex-extracted symbols, not an AST dependency analysis. All conditions have the same caps and worker instructions. Neither policy receives task IDs or hidden test results. The heuristic is an unproven starting candidate, not a new state-of-the-art claim.

Begin with the periodic policy on `click2068_1_6` to validate the full model-to-Judge path. Continue with the other frozen pairs and controls after the path works. Retain every started run. Infrastructure fixes require a new run identifier and an explicit accounting note; never discard an unfavorable score. Any policy, budget, or worker change starts a separately labeled condition.

## Feedback and grading

Workers can inspect original source/tests and create public tests. Public integration checks run only original public targets plus candidate public tests; they never load hidden feature tests or reference patches. Final grading restores original tests, injects the task-owned feature suites, and independently scores both features on the final integrated patch. Primary outcome is both-feature correctness. Also report individual feature results, merge behavior, public checks, token usage, tool time, and elapsed time. No LLM judges correctness.

Worker protocol or code failures retain the last successfully harvested patch and receive final grading. Infrastructure interruptions, missing token telemetry, or budget overruns are reported separately as incomplete/unscored; diagnostic grading must not turn them into valid model accuracy. Attributed code/test failures remain failures. Frozen patch allowlists, unprivileged test execution, immutable grader assets and expected test identities/counts prevent common evaluator shortcuts. The one known dynamically generated UUID parameter is normalized without removing any case. Candidate Python still executes within the test interpreter; this is not a complete defense against malicious in-process evaluator manipulation.

## Interpretation and progression

Separate inability to implement individual features from integration failures; a very low score alone does not establish a coordination challenge. Near-floor performance requires checking worker competence and budget sufficiency. Near-ceiling performance is reported honestly and motivates broader independently selected coverage or a cost-at-fixed-success study, not tighter budgets or deleting successful cases. Do not claim that most models fail from one model's three-pair pilot.

The intended reproducible study uses a pinned open-weight coding model, enforceable aggregate token limits, repository-disjoint development/evaluation manifests, and strong team, unconditional-checking, serial and centralized controls. The local action proxy is not the complete official CooperBench team harness. The research contribution is an outer-loop task for learning allocation of public executable verification and repair under a shared budget; the submitted artifact is a reusable policy, not manually authored solutions to benchmark cases.

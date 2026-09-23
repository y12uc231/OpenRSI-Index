# TeamBench source audit for an OpenRSI task

Read-only audit, 2026-09-23. No fetched code was executed. Official repository pinned to [`ybkim95/TeamBench@d185aef1916fd86a9ba554d581fd256319a973af`](https://github.com/ybkim95/TeamBench/tree/d185aef1916fd86a9ba554d581fd256319a973af). Selected source snapshots are under `research/teambench-source/`; full recursive tree is `research/teambench-tree.json` (`truncated=false`, 4,392 paths).

**Verdict:** substantively attractive research substrate, but this public pin is not a verified, secure, drop-in OpenRSI environment. The next concrete deliverable should be a small audited task manifest and role-isolated runner, then a fixed-budget baseline run. Do not promise a ready 89-task benchmark or unseen-family evaluator from the README alone.

## Official baseline contracts

| Baseline | Actual source behavior | Research use |
|---|---|---|
| `full` | Planner → Executor → Verifier; verifier failure triggers Executor repair and re-verification, default two remediation attempts. Fresh loops use persisted workspace/messages. | Primary official repair baseline; already much stronger than a one-call team. |
| `topo_iterative` | Three Planner ↔ Executor rounds; each role gets `max_turns // 3` turns per round. Ends with automatically passing attestation; **no Verifier**. | Useful planning-feedback topology control, not an official verification/recovery loop. |
| `oracle_2pass` | Full-information solo agent plans then executes in separate phases, each up to `max_turns`. | Strong centralized control. |
| `oracle_cot` / `topo_self_check` | Structured solo planning or implement → verify → fix, up to `2 * max_turns`. | Strong compute/structured-reasoning controls. |
| `oracle_budget_matched` | Hard-coded 50 turns, justified in comment by 15 + 25 + 10. | Do not assume genuinely budget matched to default `full`: that path uses `max_turns=20` per phase and up to seven phases including repairs, hence at most 140 turns. |

Source: [`harness/ablation.py`](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/harness/ablation.py), especially lines 55–79, 246–267, 410–421, 604–712, 718–795, 1017–1059; [`harness/orchestrator.py`](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/harness/orchestrator.py), lines 109–305.

`full` already asks the Planner to transmit all requirements, the Executor to run validation, and the Verifier to provide specific actionable feedback. A new evidence-carrying scaffold must beat this baseline, not a deliberately vague-message baseline. `_select_best_workspace` has a misleading comment mentioning grading, but its implementation selects a snapshot using **total file size**, restoring one over 10% larger than the current workspace; it does not run the hidden grader (orchestrator lines 297–344).

Persisted artifacts include `messages/`, `submission/attestation.json`, per-role logs (`logs/planner`, `logs/executor/remediation_N`, `logs/verifier/attempt_N`), and workspace snapshots. Each fresh `AgentLoop` starts a fresh conversation but polls message files; optimization can alter what evidence is carried across phase boundaries. Normal source analysis and executable verifier code are appropriate allowed tools, subject to preserved role permissions and protected oracle files.

## Task set and exclusions

The official [`leaderboard_90_tasks.json`](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/leaderboard/data/leaderboard_90_tasks.json) is a **JSON object with `tasks[].task_id`**. Its metadata derives 90 slots from 100 by dropping ten broken-grader tasks:

`GH1000_numpy_19869`, `GH1001_numpy_30855`, `GH1002_scipy_24753`, `GH1003_scipy_24496`, `GH1004_dask_11665`, `GH1005_ray_60236`, `GH1008_spaCy_12749`, `GH1009_spaCy_12486`, `GH1010_great_expectati_10406`, `GH144_psycopg_1247`.

The stated reason is missing compiled dependencies despite post-PR canonical fixes in the workspaces. Additionally exclude [`GH120_redis-py_3863`](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/tasks/GH120_redis-py_3863/spec.md): explicitly under re-curation and guaranteed zero.

**Additional source inconsistency:** all 90 slots have `grade.sh`, but **31 lack `spec.md` or `brief.md` at their listed task paths** in the complete Git tree. Examples: `CR4_api_review` lacks spec; `INC1_cascade_failure`, `D6_data_reconcile`, `RDS10_survey_analysis` lack both. `setup_run` generates workspace and expected results but calls `write_to_disk` without `task_dir`; `generators/base.py` only writes generated spec/brief when that parameter is supplied. `run_ablation_condition` silently substitutes empty strings for missing spec/brief. Thus the README claim that the other 89 are fully evaluable is not established by this public source path.

Source: [`harness/run_all.py:33`](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/harness/run_all.py#L33), [`generators/base.py:61`](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/generators/base.py#L61), [`harness/ablation.py:229`](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/harness/ablation.py#L229).

Saved `research/teambench-source-complete-candidates.json` contains **58 static source-complete candidates** after these filters. This is a **file-presence shortlist, not runtime validation**. Generated workspaces may still mismatch static seed-specific specs. Proposed initial categories: cross-system integration, distributed systems, specification, adversarial requirements, software engineering. Select tasks only after clean-image dependency checks and known-correct/known-incorrect grading checks. Avoid selecting only tasks where a chosen model fails; freeze exclusion rules before model comparison.

## Critical harness gaps before OpenRSI optimization

1. **Actual role isolation:** README advertises OS-enforced Docker mounts, but the documented ablation runner creates local `RunCommandTool` instances. `RunCommandTool.execute` invokes `subprocess.run(cmd, shell=True, cwd=workspace)` with inherited environment. No Docker call appears in the inspected ablation/run_all path. Both Executor and Verifier receive it. The Executor's file-read roots additionally include the whole directory containing `brief.md`, which also contains spec and grader. A Docker Compose file existing separately does not establish enforcement for this execution path. Build a real role-specific tool gateway/container runner and verify its mount/permission contract. [Source](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/harness/agent_interface.py#L140), [role tools](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/harness/agent_interface.py#L492).
2. **Oracle protection and score integrity:** generated `expected.json` is put in `reports/`, while Executor may read/write that directory. `grade_run` executes a grader locally, then accepts existing `reports/score.json`, even after a timeout; it does not first remove a prior score or establish trusted ownership. Put expected values/grader source/score output exclusively in Judge; copy only final candidate workspace into a clean grading sandbox; fresh protected output and independently validated score schema. [Generator](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/generators/base.py#L81), [grader](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/harness/run_all.py#L88).
3. **Hard total budget:** current limits are model turns per phase, plus 60-second individual tool commands. They are not aggregate input/output/reasoning-token or whole-episode wall-clock limits. Add a trusted inference proxy measuring all worker/coordinator calls; cap total billed tokens (specify reasoning accounting), context, tool CPU/wall time, and output artifacts. Charge failed/retried calls consistently. Freeze worker/model revision and sampling parameters.
4. **Unseen families:** fresh seeds are not unseen task families. Split by generator/source lineage and upstream project; keep related variants/seeds together. Neither a frozen public 90-slot manifest nor public tasks can honestly be called contamination-free. A task-level hidden split can be hidden from the run while public globally; say so. For stronger family generalization, hold out entire generator families from scaffold optimization.
5. **Hidden evaluator is stale:** `scripts/evaluate_hidden.py` passes `task_id`, `spec_path`, workspace paths, and `model` to `run_ablation_condition`; the current function takes `task_dir`, `run_dir`, and `adapter`. It also stages once per instance before looping conditions, risking shared modified state between conditions. Do not treat this script as a ready evaluator. Use freshly staged isolated runs per condition after adapting API and seed-specific specs. [Script](https://github.com/ybkim95/TeamBench/blob/d185aef1916fd86a9ba554d581fd256319a973af/scripts/evaluate_hidden.py).

## Commands and metric contract

Official install instructions: Python >=3.10, `pip install -e '.[all]'` or `uv sync --all-extras`, then `docker compose build`. This audit did **not** install or run them. Host package base dependencies are click/PyYAML; optional SDKs are OpenAI, Anthropic, Google GenAI. Docker images use Python 3.11 slim. Executor image has minimal shell/git tools, Verifier adds pytest, pytest-cov, hypothesis, mutmut. Task graders can require additional libraries/languages; e.g. DIST1 invokes `pytest --timeout=30` without the inspected image installing pytest-timeout. Pin and preinstall task dependencies, disable runtime package retrieval, then validate. No trustworthy minimum CPU/RAM/runtime estimate was established.

Documented runner shape, **for a prepared isolated environment only**:

```bash
python -m harness.ablation --model MODEL --tasks TASK_ID --seeds 0 \
  --conditions full oracle_2pass topo_self_check topo_iterative \
  --max-turns 20 --max-remediation 2 --output results/baselines.json
```

These CLI arguments exist, but the command alone does not provide fair total budgets or security. `scripts/run_strong_baseline.py` fixes a 28-task public set and defaults to `oracle_cot oracle_2pass`; use its logic as a reference, not as the automatically validated new split.

The active ablation path calls `harness.run_all.grade_run`, not the separate `harness.grade_task` CLI. Active score fields are **`pass`** and `secondary.partial_score`; README's `passed` description is inaccurate here. Suggested primary OpenRSI score: macro-average deterministic **full task pass rate by held-out family** (predeclare family weighting). Partial score, verifier false-accept, repaired-failure recovery, tokens and runtime are diagnostics. Verifier attestation is not objective success. Recompute original comparison metrics as secondary so the adaptation is interpretable.

## Research-ready contract after the gaps are closed

Optimize evidence-bearing handoff schemas, requirement-to-test links, provenance/version tracking, context selection, adaptive verifier effort, repair routing and stopping, with ordinary symbolic test/analysis code permitted. Freeze task generation, private oracle, models, tool rights, and total budget. Require matched-budget official `full`, structured solo, simple full-refresh/retest, and evidence-scaffold baselines. Compare isolated team against centralized access to separate useful coordination from model capability or more inference.

Worker inference may use APIs or a fixed local endpoint; CPU-only environment/grading does **not** imply CPU-only inference. Repository vLLM launch scripts themselves have stale hardware comments (35B comment says two GPUs while command passes four); do not derive hardware promises from them. Select actual fixed worker and measure costs only after protocol validation. Published TeamBench weakness motivates the experiment but is not a measured baseline for this corrected new contract.

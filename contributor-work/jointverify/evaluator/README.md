# JointVerify pilot checker

This is a CPU-only wrapper around three **preselected CooperBench feature pairs**, pinned at upstream commit `63b9d44d9f39a02fccf5bf0052db48a917a011fd`. It is a pilot, not a new benchmark or evidence that current models score poorly. No model calls are made by this package.

## Interface

From the `jointverify` directory:

```python
from evaluator.checker import evaluate, get_case

result = evaluate(
    "click2068_1_6",
    {"lead": lead_diff_string, "member": member_diff_string},
    mode="public",  # or "judge" after the final submission
)
```

Patch values may also be `pathlib.Path` objects. They must be git unified diffs against the frozen base. Worker identity fixes the lead before grading. `get_case(task_id)` returns the digest-pinned image and original base commit for a private worker container. Available IDs: `click2068_1_6`, `click2800_1_3`, `dirty43_2_3`.

Optional `max_seconds=` bounds the shared wall-clock allowance across merge and test stages (plus at most three seconds per active container for forced cleanup). A deadline exhaustion is an incomplete evaluation with `validinfra=false` and a stage `budget_exhausted` flag, not a failed candidate. Run the final Judge without this public-work budget restriction.

Both modes return `validinfra`, `candidate_valid`, `merge`, `merged_patch`, and `merged_patch_sha256` when merge succeeds. A rejected patch has `candidate_valid=false` and a failed score, rather than being silently discarded. A container/asset/controller failure sets `validinfra=false`; exclude it from model-performance denominators and repair the infrastructure before rerunning.

- **Public** returns `public_passed` and `public_check` with counts, exit code and log. It loads no oracle or feature-test assets. It runs the task's original selected test files plus candidate-changed Python files under `tests/`. Public checks are integration feedback, not evidence that both requested features work.
- **Judge** returns `both_features_passed` and per-feature `feature_checks`. It strips candidate changes under `tests/`, restores pinned base tests/configuration, then applies each upstream feature's immutable test patch separately in a fresh container. Both suites must pass. The collected test identities, pass count and skip count must match the frozen oracle calibration. Candidate collection errors are valid test failures.

The existing Dirty Equals `test_is_uuid_true` case generates `uuid.uuid1()` during collection. Only that known UUID parameter is normalized when comparing case identities. Its test still runs and contributes to the exact count; all other identities remain literal.

CLI:

```sh
python3 -m evaluator.checker click2068_1_6 --lead lead.patch --member member.patch --mode public --output public.json
python3 -m evaluator.checker click2068_1_6 --lead lead.patch --member member.patch --mode judge --output judge.json
python3 -m unittest evaluator.test_checker -v
python3 -m evaluator.validate --output-dir /absolute/path/outside-this-repository/validation
```

Supply the upstream checkout using `source_root=` / `--source-root`, or set `JOINTVERIFY_SOURCE_ROOT`. Without an explicit path the fallback is `./CooperBench`. It must contain the exact hashed assets in `manifests/pilot-v1.json`; the evaluator does not install dependencies or execute upstream shell runners. Pull the three manifest image digests before running on a new host. Docker must be available. No GPU or credentials are needed for scoring.

## Merge contract

This follows the pinned upstream's three-way merge and lead-only fallback policy: each independent patch is applied to a separate base branch, then the lead branch is merged into the member branch. Byte-identical patches are applied once. An empty patch is a skipped branch. Application failure or merge conflict triggers the lead-only fallback; a clean merged tree that fails tests never gets an alternative fallback. There is no union merge, best-of-two selection, test-informed worker choice, or automatic repair. Logs disclose every fallback. Git apply first uses ordinary application, then the upstream three-way fallback; the identical-patch path may use recount. Feature-test assets use the upstream whitespace-tolerant application.

The wrapper intentionally accepts a narrower patch format than upstream: source files under the task's package and `tests/` only; no renames, deletions, binary patches, symlinks, executable new files, mode changes, hidden paths or build/configuration edits. This restriction is part of this pilot and must be disclosed in results.

## Trust boundary and limitations

Each stage uses a fresh digest-pinned Docker image, no network, two CPUs, 2 GiB memory, 256 process limit, and a bounded timeout. The host mounts only the required input assets read-only. Public runs never mount grading assets. Pytest runs as unprivileged UID 65534; source/tests are root-owned, Git metadata is inaccessible to pytest, and only the trusted root controller can write the host result directory. Candidate output text cannot claim a passing score: the controller checks subprocess exit status and JUnit data against oracle case coverage. The image's existing Python environment is used without pip/network changes.

This hardens ordinary accidental contamination and straightforward report edits. **It does not prove security against adversarial Python code**: candidate code executes inside the same interpreter as pytest, can read tests while they execute, and may try to forge JUnit or interfere with pytest internals. A submission intended for adversarial reward-hacking research needs a separate hardened grader design. The published upstream tests and reference patches are public on GitHub; workers therefore need the root runner's network-disabled private workspaces, stripped Git history, and no mounts of this evaluator/source checkout. Judge logs are final metrics, not feedback for revising the same held-out submission.

The oracle is upstream `combined.patch`, which can implement additional features beyond the selected pair. It validates that the environment and selected tests can pass; its score is not a model baseline. Independent single-feature gold patches provide an integration control, not an agent score. The three pairs cover only two Python repositories and were selected for cheap execution, so do not extrapolate their results to CooperBench overall.

## Frozen assets and control evidence

`manifests/pilot-v1.json` freezes the pair IDs, base commits, image digests and input hashes. `manifests/judge-expectations-v1.json` freezes oracle test identities and counts from pre-model CPU calibration. Companion SHA-256 files detect accidental edits. These are reproducibility checks, not signatures against a party who can modify the whole checkout.

`validation/summary.json` contains actual local Docker base/oracle/public/integration control counts, input hashes and execution metadata. It contains no model results. Full raw control outputs remain outside this checkout because they include upstream reference code and test traces; the current packet publishes the aggregate evidence without redistributing those assets. Base and oracle are rerunnable with `python3 -m evaluator.validate --output-dir /absolute/local/evidence`; the command never changes frozen expectations. The recorded source hashes describe the execution-time revision; later reporting-path changes do not rewrite historical evidence.

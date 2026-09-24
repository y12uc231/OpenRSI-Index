# JointVerify

**Can coding agents learn when a joint test is worth its cost?**

JointVerify is an OpenRSI task under development: an outer research agent improves a reusable policy that allocates a fixed team budget between implementation, public integration tests, and repair. Two frozen coding workers implement interacting features in real repositories. Final correctness is measured by executable feature tests withheld from the workers.

This repository contains original orchestration, budget accounting, policy controls, and a hardened pilot evaluator around existing CooperBench tasks. The underlying software problems and feature tests are CooperBench's work. The contribution is the proposed research/evaluation contract and its executable adapter, not a claim to have invented multi-agent coding or a wholly new task dataset.

## What exists

- Two isolated coding workspaces with explicit messages and versioned peer patches. Workers can read/edit/test code and integrate each other's changes.
- Three public-check allocation policies: periodic, unconditional and a dependency heuristic. The heuristic is a candidate, not an established improvement.
- Trusted model-call, token and tool-time accounting, including retries/failed attempts if invoked; local Codex and reproducible endpoint lanes are labeled separately.
- Three frozen real-code feature pairs, pinned source assets and image digests, and separate public versus final grading paths.
- Executed positive/negative evaluator controls and offline tests. See [validation evidence](evaluator/validation/summary.json).

## Why this is a research task

The manipulated component is the verification/repair policy, not worker weights or per-case manual patches. Development trajectories can train a risk predictor or decision policy. Judge runs the materialized policy on fixed repository-transfer cases with the same worker model, tools and aggregate resources as the reference policy. Both-feature completion is the primary outcome; inference usage, checking cost and merge behavior explain it.

The hypothesis is that a policy can exploit changed dependencies and the age of previous test evidence to spend checks where they prevent integration failures, outperforming competent fixed schedules at equal budgets. It may fail: unconditional checking or serialization could be as good. Those outcomes still answer the question.

CooperBench already studies coordination prompts, and Claim Plane already studies dependency-aware admission and serialization. Our narrower research axis is **learning allocation of executable public verification and repair under a shared inference/test budget, with repository transfer**. This is a bounded novelty finding, not a guarantee that no related method exists. See the [source audit](../multi-agent-evals/COOPERBENCH-SOURCE-AUDIT.md) and [research review](../multi-agent-evals/RESEARCH.md).

## Local pilot

Read [the preregistered protocol](PILOT-PROTOCOL.md) before interpreting any run. The three-pair local pilot measures feasibility using the current local Codex deployment. It is not a cross-model comparison, an immutable open-weight baseline, or a token-matched study. Results must distinguish model performance from infrastructure controls.

From this directory, with the pinned CooperBench source checkout and manifest images available:

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest evaluator.test_checker -v
python3 -m evaluator.validate --help
python3 runner/episode.py \
  --source /absolute/path/to/CooperBench \
  --task click2068_1_6 --policy periodic \
  --output /absolute/path/outside-this-repository/run-001
```

Use `--mock` for an explicitly labeled no-model controller check. Raw model events and local paths stay outside the Git checkout. Public results contain only reviewed, allowlisted evidence.

## Limits that matter

The pilot covers two Python repositories and uses a narrower action proxy than the complete official CooperBench team harness. Low scores cannot establish that most models fail; high scores will be retained. The final study needs strong centralized, serial, official-team and unconditional-verification comparisons, a frozen open-weight server, and a repository-disjoint workload. The evaluator reduces accidental leakage and simple tampering but does not claim complete protection from malicious Python executed inside pytest.

The official OpenRSI contribution is a proposal before baseline reproduction. Work here establishes a concrete implementation path and honest evidence; it does not replace the required proposal review or contributor publication metadata.

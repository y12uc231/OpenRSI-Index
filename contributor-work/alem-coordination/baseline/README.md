# Portable native Alem CPU baseline

This package reproduces one **unchanged, pretrained HyperMARL-IPPO policy** on all 20 native Hard worlds, seeds 9999–10018. The completed run achieved **18.930817916989326% normalized coordination reward** in 170.381939167 seconds of Docker wall time. This is a reward fraction, not a success rate. It establishes an inexpensive baseline for further research; it does not demonstrate that contemporary language models perform poorly on a new task.

The three inner agents are recurrent reinforcement-learning policies with local observations and four native communication actions. No language model, training, controller, action override, mid-episode reset, or shortened episode is involved. One fixed training seed is evaluated; this does not estimate training-seed variance.

## Reproduce

Use Python 3.11+ on the host, Git, Docker with at least four CPUs and 6 GiB available, and about 1 GiB for the public source/checkpoint plus several GiB for the image. Network access is used only during explicit acquisition and image construction. Evaluation has no network or credentials. From this directory:

```sh
python3 acquire.py
python3 build.py
python3 replay.py --run-id native20-reproduction-001
python3 summarize.py .work/results/native20-reproduction-001/result.json \
  --launch .work/results/native20-reproduction-001/launch.json
```

All paths are resolved relative to this package or the optional `--work` directory. Acquisition downloads exactly one public checkpoint, **224,560,898 bytes in 20 files**, and a pinned upstream checkout. Every asset byte and all 291 tracked source files are verified before build/replay and again after replay. Existing changed assets are rejected. Results are never overwritten; use a distinct run ID. A failed run is retained and unscored; there are no silent retries or substitutions. `.work/` is ignored by Git. Do not commit weights, downloaded upstream source, or new raw logs.

The recorded successful platform is **Linux/arm64, Python 3.12.14**, four CPU cores and 6 GiB, with JAX/JAXlib 0.4.38. The Dockerfile pins the original Python image digest and recorded dependency versions. It reconstructs a new image; its image ID is not claimed to equal the original build. Package versions are locked, but Python wheel hashes and the whole original OCI image are not distributed. Other CPU architectures and rebuilds have not had a full rollout validated. `build.py` prints the actual image identity and architecture. To use an existing verified image, pass its name or digest with `replay.py --image`.

The launcher sets a 1,800-second operator deadline, a read-only container root, no extra capabilities, no network, a 256-process ceiling, and 1 GiB temporary storage. Only dedicated results and temporary storage are writable. Upstream source, checkpoint and wrapper are read-only mounts. The upstream package builds a texture cache at import even in symbolic evaluation; the wrapper copies its unchanged package to container-only temporary storage so this succeeds. The first feasibility attempt failed before evaluation because its source was read-only; [attempts.json](evidence/attempts.json) preserves that failure.

## Frozen provenance and configuration

- [Official Alem source](https://github.com/alem-world/alem-env/tree/14d412e5ee961f9c43d6ce92ee05fee9cd1efc5e): release v0.2.1, commit `14d412e5ee961f9c43d6ce92ee05fee9cd1efc5e`.
- [Released checkpoint](https://huggingface.co/alem-world/alem-rl-baselines/tree/9493179ea5e86cd625add66c0f88e23f04f928b5/1B/hypermarl-rnn/hard/seed0): HyperMARL-IPPO, 1B training steps, Hard, training seed0; immutable Hub revision `9493179ea5e86cd625add66c0f88e23f04f928b5`. The release metadata report 25,614,013 parameters. Optimizer state is present in the artifact but is never updated.
- [Source hashes](source-manifest.json), [checkpoint hashes](asset-manifest.json), [runtime versions](requirements.lock), [original provenance](evidence/provenance.json), and [protocol declared before the run](evidence/declared-protocol.md).

This is a **fresh current-config baseline**, not replication of the historical 17.6% result and not an improvement over it. The checkpoint's historical training configuration enables base-difficulty scaling and names an older internal environment version. Released reload overrides omit that setting and current v0.2.1 YAML defaults it to false. This run explicitly fixes `SCALE_BASE_DIFFICULTY=false`, before its outcomes were observed. The coordination preset remains Hard; baseline mob-health and starting-resource scales remain 1× rather than the scaled-Hard 1.3× and 0.7×. The complete effective config and its SHA256 are retained. Do not silently substitute historical scaling in this replay.

The wrapper calls the official `single_run` checkpoint-loading branch and observes native evaluator output. It checks architecture-critical settings, preserves action masking, deterministic categorical mode, per-agent recurrent state, and native randomness. The official sequential evaluator resets world `9999 + episode_index`, but its transition RNG continues between episodes. A policy that changes episode length can therefore change subsequent transition draws, even with identical world seeds. These are native semantics; this package does not relabel them as paired common-random-number trials.

## Completed result and limitations

All native metrics and all 20 per-world rows are preserved exactly in [native20.json](evidence/native20.json). [summary.json](evidence/summary.json) contains world-level dispersion; [subcategories.json](evidence/subcategories.json) retains all native coordination, cooperation and death diagnostics. Native aggregate standard errors use the upstream calculation; the summary additionally reports **sample** SD/SE, so the two SE conventions differ slightly.

| Reward, normalized to the native maximum | Mean across 20 worlds | Sample SD |
| --- | ---: | ---: |
| Coordination | 18.930817916989326% | 2.927987490513376 points |
| Base | 15.576037019491196% | 4.7951450302275695 points |
| Total | 16.99468120932579% | 2.832954585337623 points |

The native coordination subcategory reward fractions are **13.46590921282768% hard synchronized**, **24.375001937150956% soft coordination**, **85% handover**, and **0% construction**. Each has its own achievement/reward denominator; these are neither disjoint percentages of total reward nor event success rates. The high handover fraction must be preserved rather than described as universally poor coordination.

| Native event diagnostic | Mean per world |
| --- | ---: |
| Synchronized successes / attempts | 4.7 / 12.5 |
| Handover successes / setups / expiries | 1.5 / 4.55 / 2.95 |
| Construction successes / attempts | 0 / 0 |
| Elite-combat successes / attempts | 0 / 2.4 |
| Trades | 6.7 |

Construction was never attempted, so its zero may reflect exploration, prerequisites or survival instead of inability to coordinate an available construction attempt. Native mean per-episode event rates are also retained: sync 0.568683098629117 and handover 0.4479762017726898. An average of episode ratios need not equal a ratio of the mean counts above.

All 20 episodes terminated naturally **with all three agents dead**, not with task completion. They ran 272–1,176 transitions, under the unchanged 10,000-step cap. Mean terminal death counts are 1.65 from mobs, 0.95 starvation, 0.35 dehydration and 0.05 friendly fire. Boss-defeat achievements are zero. Basic survival therefore limits these results alongside coordination; low reward is not pure evidence of a coordination-only failure.

There were 9,428 joint environment transitions. Native evaluation including JIT took 67.44778361300268 seconds (139.78220624854538 transitions/second), the entire Python process took 164.8959330739999 seconds, and Docker wall time was 170.381939167 seconds. Peak process RSS was 4,596,140 KiB. Import/cache construction and checkpoint restoration are included in the full timing. This is a measured cold run, not a separate estimate of warmed steady-state throughput.

The checkpoint is the paper's strongest released algorithm and fixed seed0, not a deliberately weak algorithm or seed selected for low scores. This single-checkpoint run does not replace a multiple-training-seed comparison or establish novel method-level research. The source's MIT license and the checkpoint's published terms apply to fetched assets. This repository contains acquisition metadata and a replay wrapper, not redistributed weights or upstream source.

## Offline package checks

```sh
python3 -m unittest discover -s tests -v
python3 acquire.py --verify-only
```

These checks validate provenance, retained results, manifest boundaries and launch settings. They do not rerun the policy.

# Portable native Alem CPU baseline

This package evaluates one **unchanged, pretrained HyperMARL-IPPO policy** on all
20 native Hard worlds, with seeds 9999–10018. The completed run achieved
**18.930817916989326% normalized coordination reward** in 170.381939167 seconds
of Docker wall time. The percentage measures reward relative to the native
maximum; it is not a success rate.

A policy is the trained model that chooses actions. A checkpoint is the saved
model and training state used to restore it. Only the policy runs here; its
weights and training state are never updated.

The three game agents are recurrent reinforcement-learning policies. Each has
local observations and four native communication actions. This evaluation uses
no language model, training, added controller, action override, mid-episode
reset or shortened episode. It provides an inexpensive starting measurement
for research. It does not show that current language models perform poorly.

Only one fixed training seed is evaluated, so the result does not measure
variation between separately trained policies.

## Reproduce

You need Python 3.11+ on the host, Git, Docker with at least four CPUs and 6 GiB
available, about 1 GiB for the public source and checkpoint, and several GiB for
the image. Downloads and image construction use the network. Evaluation has
no network access or credentials.

From this directory, run:

```sh
python3 acquire.py
python3 build.py
python3 replay.py --run-id native20-reproduction-001
python3 summarize.py .work/results/native20-reproduction-001/result.json \
  --launch .work/results/native20-reproduction-001/launch.json
```

Paths are relative to this package or the optional `--work` directory.
Acquisition downloads one public checkpoint—**224,560,898 bytes in 20 files**—and
an upstream checkout pinned to a specific commit. Every asset byte and all 291
tracked source files are verified before build and replay, then again after
replay. Changed assets are rejected.

Use a new run ID for every attempt: results are never overwritten. Failed runs
are retained and left unscored, with no silent retries or substitutions.
`.work/` is ignored by Git. Do not commit weights, downloaded upstream source
or new raw logs.

The successful run used **Linux/arm64, Python 3.12.14**, four CPU cores, 6 GiB
of memory, and JAX/JAXlib 0.4.38. The Dockerfile pins the original Python image
digest and the recorded dependency versions. A rebuild creates a new image;
its image ID is not guaranteed to match the original. Package versions are
locked, but Python wheel hashes and the complete original OCI image are not
distributed. Full evaluation has not been validated on other CPU architectures
or independent rebuilds.

`build.py` prints the actual image identity and architecture. To use an existing
verified image, pass its name or digest with `replay.py --image`.

The launcher allows 1,800 seconds. It uses a read-only container root, no extra
capabilities, no network, a 256-process limit and 1 GiB of temporary storage.
Only dedicated results and temporary storage are writable. The source,
checkpoint and wrapper are mounted read-only.

The upstream package builds a texture cache when imported, even during symbolic
evaluation. The wrapper therefore copies the unchanged package into temporary
storage inside the container. The first feasibility attempt failed before
evaluation because its source was read-only; that failure is retained in
[attempts.json](evidence/attempts.json).

## Recorded source and configuration

- [Official Alem source](https://github.com/alem-world/alem-env/tree/14d412e5ee961f9c43d6ce92ee05fee9cd1efc5e): release v0.2.1, commit `14d412e5ee961f9c43d6ce92ee05fee9cd1efc5e`.
- [Released checkpoint](https://huggingface.co/alem-world/alem-rl-baselines/tree/9493179ea5e86cd625add66c0f88e23f04f928b5/1B/hypermarl-rnn/hard/seed0): HyperMARL-IPPO, 1B training steps, Hard, training seed 0; immutable Hub revision `9493179ea5e86cd625add66c0f88e23f04f928b5`. The release metadata report 25,614,013 parameters. The artifact includes optimizer state, which is never updated.
- [Source hashes](source-manifest.json), [checkpoint hashes](asset-manifest.json), [runtime versions](requirements.lock), [original provenance](evidence/provenance.json), and [protocol declared before the run](evidence/declared-protocol.md).

This is a **new measurement under the current configuration**, not a replication
of the historical 17.6% result or evidence of improvement over it. The checkpoint
was trained with base-difficulty scaling enabled and an older internal
environment version. The released reload overrides omit that setting, and
the current v0.2.1 YAML defaults it to false.

Before observing outcomes, this run fixed `SCALE_BASE_DIFFICULTY=false`. The
coordination preset is still Hard. Mob health and starting resources both use
their 1× baseline scales, rather than the scaled-Hard values of 1.3× and 0.7×.
The complete effective configuration and its SHA256 are retained. Reproduction
must keep this setting; substituting historical scaling would change the
experiment.

The wrapper uses the official `single_run` checkpoint-loading branch and reads
the native evaluator's output. It checks settings that determine the policy
architecture and preserves legal-action masking, deterministic categorical
mode, each agent's recurrent state, and native randomness. Here, categorical
mode means selecting the highest-probability legal action rather than sampling.

The official evaluator starts each world at seed `9999 + episode_index`, but its
transition random-number stream continues across episodes. Changing an earlier
episode's length can therefore change random draws in later episodes, even when
world seeds stay the same. This package preserves that behavior. Its results
should not be described as paired trials with identical random draws for each
policy.

## Completed result and limitations

All native metrics and all 20 world records are preserved exactly in
[native20.json](evidence/native20.json).
[summary.json](evidence/summary.json) reports variation across worlds, and
[subcategories.json](evidence/subcategories.json) retains the native
coordination, cooperation and death diagnostics. Native aggregate standard
errors follow the upstream calculation. The summary also reports **sample**
standard deviation (SD) and standard error (SE), so the two SE conventions
differ slightly.

| Reward, normalized to the native maximum | Mean across 20 worlds | Sample SD |
| --- | ---: | ---: |
| Coordination | 18.930817916989326% | 2.927987490513376 points |
| Base | 15.576037019491196% | 4.7951450302275695 points |
| Total | 16.99468120932579% | 2.832954585337623 points |

The native coordination subcategory scores are **13.46590921282768% hard
synchronized**, **24.375001937150956% soft coordination**, **85% handover**, and
**0% construction**. Each uses its own achievement/reward denominator. They are
not event success rates or separate shares that add up to total reward. The
strong handover result matters: these results do not show poor performance in
every kind of coordination.

| Native event diagnostic | Mean per world |
| --- | ---: |
| Synchronized successes / attempts | 4.7 / 12.5 |
| Handover successes / setups / expiries | 1.5 / 4.55 / 2.95 |
| Construction successes / attempts | 0 / 0 |
| Elite-combat successes / attempts | 0 / 2.4 |
| Trades | 6.7 |

Construction was never attempted. Its zero could reflect limited exploration,
missing prerequisites or early death, rather than failure to coordinate an
available construction attempt. The native mean per-episode event rates are
also retained: sync 0.568683098629117 and handover 0.4479762017726898. Averaging
the individual episode ratios need not give the same answer as dividing the
mean counts in the table.

All 20 episodes ended naturally **with all three agents dead**; they did not
end through task completion. They lasted 272–1,176 transitions, below the
unchanged 10,000-step cap. Mean terminal death counts were 1.65 from mobs, 0.95
from starvation, 0.35 from dehydration and 0.05 from friendly fire. Boss-defeat
achievements were zero. Survival problems therefore limit reward alongside
coordination problems. Low reward cannot be attributed only to coordination.

Across the run there were 9,428 joint environment transitions:

| Timing or memory measure | Recorded value |
| --- | ---: |
| Native evaluation, including just-in-time compilation (JIT) | 67.44778361300268 seconds |
| Native evaluation throughput, including JIT | 139.78220624854538 transitions/second |
| Entire Python process | 164.8959330739999 seconds |
| Docker wall time | 170.381939167 seconds |
| Peak process resident memory (RSS) | 4,596,140 KiB |

The full timing includes imports, cache construction and checkpoint restoration.
This was a cold run; it does not separately measure steady-state throughput
after initialization.

The checkpoint uses the paper's strongest released algorithm and fixed training
seed 0. It was not chosen as a weak algorithm or selected for a low score.
One checkpoint cannot replace a comparison across training seeds or establish
a new research method.

The source's MIT license and the checkpoint's published terms apply to downloaded
assets. This repository supplies acquisition metadata and a replay wrapper;
it does not redistribute the weights or upstream source.

## Offline package checks

```sh
python3 -m unittest discover -s tests -v
python3 acquire.py --verify-only
```

These checks verify the recorded sources, retained results, which files the
manifests cover, and launch settings. They do not rerun the policy.

# Deployment validation records

The corrected runtime was validated on **24 September 2026**. In one ordinary
container, it passed the operating-system isolation probe, then evaluated the
pass-through reference and the unchanged final Sol controller consecutively.
Each ran on the same 20 prescribed worlds.

All **40 trajectories** matched their original Docker evaluations exactly.
The comparisons cover trajectory hashes, every native metric, steps, actions,
overrides, and completion states. A trajectory hash is a fingerprint of the
recorded game state, recurrent policy state, actions, and other transition data.

| Corrected-runtime check | Worlds | Coordination reward fraction | Invocation time |
| --- | ---: | ---: | ---: |
| Pass-through reference | 20/20 | 0.18522013239562513 | 125.29 s |
| Unchanged final Sol controller | 20/20 | 0.19465409219264984 | 128.68 s |

The full sequence took **255.69 seconds**, including the probe and container
startup, at **4 CPUs / 16 GiB** with zero GPUs. Networking was disabled and no
capabilities were added. There were no model calls or automatic retries.
See [post-audit-validation.json](post-audit-validation.json) for exact hashes,
per-world comparisons, resource limits, and test accounting, and the
[audit report](../../AUDIT.md) for the corrections.

These scores are normalized rewards: the fractions above correspond to
18.5220% and 19.4654%. They are not accuracies or successful-episode rates.
Deployment checks are not new researcher attempts or independent performance
samples.

## Original native measurements

The records below describe the native runtime **before the audit corrections**.
They retain their original source identities and are not relabeled as evidence
for the corrected code.

| Original check | Matching original trajectories | Coordination reward fraction | Outer-container time |
| --- | ---: | ---: | ---: |
| Pass-through reference | 20/20 | 0.18522013239562513 | 145.39 s |
| Unchanged final Sol controller | 20/20 | 0.19465409219264984 | 130.38 s |

The reference time includes container startup, source verification, compilation,
and all episodes. Both checks used one ordinary container capped at four CPUs
and sixteen GiB, with networking disabled and no added capabilities. Neither
used LLM calls or training steps.

The original Sol record contains exactly one additional deployment replay of
its final artifact. Its candidate SHA-256 is:

```text
3862d57dbf57dbb8e1f2efff6cd32a345dd7006a0dab58d40b45e0ff5ae38d89
```

That replay changed neither the controller nor the then-current native runtime.
All 20 complete state/policy-state/action trace hashes, native metric
dictionaries, steps, override counts, action counts, and completion states
matched the original Docker evaluation. Every world is retained in the record,
and the replay is listed in the attempt ledger.

The same behavior was reproduced by the corrected runtime:

| Recorded activity | Pass-through | Sol |
| --- | ---: | ---: |
| Joint environment steps | 8,489 | 9,571 |
| Actor callbacks | 25,467 | 28,713 |
| Action overrides | 0 | 1,009 |
| Native communication actions | 386 | 872 |

## Files in this bundle

| File | Contents |
| --- | --- |
| [post-audit-validation.json](post-audit-validation.json) | Corrected-runtime probe, two consecutive evaluations, all per-world comparisons, source/runtime hashes, and the thirteen-test native regression result |
| [full20-pass-through.json](full20-pass-through.json) | Original reference run: all native metrics, traces, costs, source/checkpoint/runtime hashes, and parity checks |
| [sol-final-deployment-parity.json](sol-final-deployment-parity.json) | Original single replay of Sol's unchanged final controller |
| [attempt-ledger.json](attempt-ledger.json) | Original integration attempts, including the initial infrastructure rejection, one-world trace mismatch, and Sol replay |
| [isolation-and-invariants.json](isolation-and-invariants.json) | Original arm64 isolation probe and six offline checks |
| [MANIFEST.json](MANIFEST.json) | SHA-256 hashes of the public evidence files |

The original six-test record does not certify later source changes. The
corrected runtime has thirteen native regressions and its own fresh kernel
probe. Its validation is recorded separately from the original attempt ledger.
The code has x86_64 and aarch64 syscall tables, but these records establish
actual kernel execution only on arm64.

## Limits and privacy

The original Docker researcher pilot records remain separate. Exact trajectory
matches establish parity for the controllers measured here; they do not prove
identical behavior for every possible controller. In particular, the native
route permits only one fixed writable scratch file per actor, so general
temporary-file APIs differ from the original Docker workers.

Judge still receives the **complete Work snapshot**. Private actor filesystems
do not independently establish trust in inherited Python or platform libraries.
Full generated Harbor and 24-hour RSI-Harness validation remain downstream
steps.

This bundle excludes private paths, commands, prompts, reasoning, events, and
logs. Hashes of the private raw results and operator records connect these
allowlisted exports to the original measurements without publishing those
private records.

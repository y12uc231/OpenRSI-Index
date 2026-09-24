# Native deployment validation

**Current corrected runtime:** see [post-audit-validation.json](post-audit-validation.json)
and the [audit report](../../AUDIT.md). The original records below retain their
original source identities. After import/staging corrections, a fresh minimal
container passed the kernel probe and then ran reference plus unchanged Sol
consecutively: all 40 original trajectory hashes, metrics, steps, actions,
overrides and completion states match exactly. Invocation times were 125.29 s
and 128.68 s; the full sequence took 255.69 s. No model calls or retries occurred.

The final native pass-through run scored all 20 declared worlds and reproduced all 20 frozen Docker baseline state/latent/action trace hashes exactly. The mean native coordination reward fraction is **0.18522013239562513** (18.5220% of the native normalized maximum). This is a baseline reward, not an accuracy or successful-episode rate.

The final run took **145.39 seconds** including container startup, source verification, compilation and all episodes, on one ordinary container capped at **4 CPUs / 16 GiB**, with network disabled and no added capabilities. It executed 8,489 joint steps, 25,467 actor callbacks, 386 native communication actions and zero overrides. There were no LLM calls or training steps.

- `full20-pass-through.json`: every world's full native metric dictionary, trace and costs; fixed source/checkpoint/runtime hashes; exact-parity checks and measured resources.
- `attempt-ledger.json`: all saved native integration/evaluation attempts, including the initial infrastructure rejection and one-world hash mismatch. These deployment-development outcomes are not researcher/model difficulty evidence.
- `isolation-and-invariants.json`: actual arm64 isolation probe and six offline checks. The code also defines an x86_64 seccomp table; this record does not claim an actual x86_64 kernel test.
- `MANIFEST.json`: SHA-256 hashes of this public evidence bundle.

Original Docker researcher pilot records remain separate. Exact pass-through parity does not prove equivalence for every possible controller, particularly controllers relying on temporary-file APIs. The native route permits only one fixed writable scratch file per actor. The complete Work snapshot still enters Judge; the actor jails do not establish independent trust in inherited platform libraries.

No private paths, commands, prompts, reasoning, events or logs are included. Private raw-result/operator hashes link these allowlisted exports to the recorded local measurements.

## Unchanged final Sol controller replay

`sol-final-deployment-parity.json` records exactly one additional deployment check of the unchanged final Sol controller (SHA-256 `3862d57dbf57dbb8e1f2efff6cd32a345dd7006a0dab58d40b45e0ff5ae38d89`). All **20/20** full state/latent/action trace hashes, all native metric dictionaries, steps, override counts, action counts and completion states match its original Docker evaluation exactly.

The score remains **0.19465409219264984**, with 9,571 joint steps, 28,713 actor callbacks, 1,009 overrides and 872 native communication actions. The single native replay took **130.38 seconds** at the same four-CPU / sixteen-GiB limits. It made no LLM calls and changed neither the controller nor the native runtime. This is deployment parity evidence, not another researcher attempt or an independent performance replicate. Every world is retained in the artifact and the replay appears in the attempt ledger.

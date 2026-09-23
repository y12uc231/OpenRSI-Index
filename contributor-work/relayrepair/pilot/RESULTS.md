# RelayRepair v0.1: measured local Codex smoke test

**Decision: reject this version as the main difficult OpenRSI contribution.** The model team, centralized model, and symbolic program all solve it perfectly. This is a useful diagnostic and harness validation; it does not demonstrate the requested model weakness.

Execution: 2026-09-23; requested local Codex model `gpt-6-astra`, reasoning effort `ultra`. The CLI did not expose an immutable model snapshot. Code and case hashes were frozen before the substantive calls; they were unchanged when the run completed. [Protocol](PROTOCOL.md); [original code commit](https://github.com/y12uc231/OpenRSI-Index/commit/a3982d3); [machine-readable results](results/local-codex-001/results.json).

| Measured configuration | Exact optimal plans | Feasible plans |
| --- | ---: | ---: |
| Three workers + coordinator, initial state | 12/12 | 12/12 |
| Three workers + coordinator, after revision and stale-message replay | **12/12** | **12/12** |
| Centralized model with the full final evidence history | **12/12** | **12/12** |
| Symbolic highest-revision baseline, same visible card strings | 12/12 | 12/12 |
| Scripted frozen initial plan, after revision | 8/12 | 8/12 |

The final model team and centralized model each score 4/4 on all three predefined strata: an update changes the optimal plan; an alternative support preserves it; and an irrelevant update leaves it unchanged. The 8/12 frozen control reflects those two unchanged strata, not genuine recovery. Scripted results are programs, not additional model evaluations.

Nine substantive model calls completed. Every emitted item lifecycle event was audited; no tool call was observed. No answer retry, best-of-N selection, case removal, or post-result difficulty adjustment occurred. Approximate elapsed time was 305 seconds, measured from manifest file creation to final results; parallel worker calls explain why summed call durations are longer (678 seconds). CLI-reported usage totals: 136,822 input tokens, 21,311 output tokens, including a separately reported 10,403 reasoning-output tokens. These fields are reported as exposed; do not add the reasoning count again to output tokens. Dollar cost was not measured.

Each worker received only its own observation cards, public plans, and in round one the explicitly relayed prior team messages. The coordinator received worker messages and public plans. The centralized control received the complete visible card history. Model prompts were assembled from the oracle-free observations file; structured oracle answers were used by the local scorer. Empty ephemeral working directories and tool-free audited calls prevented model access to the evaluator files. All 12 cases were batched together per role, so these are not 12 independent model trials. This was a controlled replay of stale messages, not a live asynchronous-network experiment.

Important limitations: one requested model, one run, a fixed small dependency graph, explicit source IDs and revision numbers, four possible plans, and simple numeric predicates. The initial state always makes the highest-utility plan feasible. All evidence fits comfortably in the messages. The pilot has no hard token budget and the centralized control uses fewer calls, so it is not a matched-compute comparison. It tests only a narrow tool-free condition; the strong general-purpose symbolic solution remains allowed in the intended research setting.

Protocol bookkeeping: the pre-run manifest recorded source, case, prompt-builder, adapter and protocol hashes. Model settings were recorded per call. The UTC-start sidecar and per-prompt hashes were not separately recorded before inference as the prose protocol requested; prompt hashes are in the post-run public manifest. Exact prompts were saved before each call. This affects provenance completeness, not the scored cases. The wrapper's stricter duplicate/missing-case rejection differed from the prose's per-case error rule, but no such output occurred. These deviations are disclosed rather than silently relabeling the run fully compliant.

The public artifact allowlist includes synthetic prompts, structured final answers, schemas, sanitized usage/settings metadata, scores and hashes. It excludes raw event streams, internal thread identifiers, local stderr, credentials and reasoning events. No original conversation trajectory was uploaded.

A future harder benchmark would need substantive uncertainty in evidence acquisition and relevance, varied held-out dependency structures, and a strong extract-and-solve baseline. It must be preregistered as a new study. Increasing complexity until this model produces low scores would not validate the desired scientific claim.

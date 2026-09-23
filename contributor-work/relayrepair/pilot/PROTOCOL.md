# RelayRepair pilot protocol — registered before substantive model runs

Registration date: 2026-09-23. This protocol is a one-model feasibility smoke test, not a benchmark leaderboard, a multi-model difficulty claim, or a formal OpenRSI proposal. Generic adapter/CLI capability checks are not substantive task runs and are excluded from scoring.

## Question and decision rule

Can three separately prompted workers and one leader preserve the correct highest-utility feasible experiment plan when authoritative evidence changes and clearly tagged older reports arrive afterward?

The purpose is to discover whether this small diagnostic has any measurable headroom. A perfect result is useful evidence against pursuing this version as an ambitious difficult task. We will report it without increasing difficulty after seeing the outcomes. Poor results, if any, will be investigated for prompt, schema, batching, or infrastructure problems before interpretation.

## Frozen cases and assets

There are exactly 12 synthetic cases: `relayrepair_01` through `relayrepair_12`, in that order. Their seeds are `[1103, 2207, 3301, 4409, 5501, 6607, 7703, 8803, 9901, 10103, 11113, 12109]`.

- Cases 01, 04, 07, 10: required support is lost and the optimum changes.
- Cases 02, 05, 08, 11: an alternative support survives.
- Cases 03, 06, 09, 12: the revision is irrelevant to the optimum.

Each case has four plans with unique utilities. Three nonfallback utilities are sampled from 11–99; an always-eligible fallback has utility 1–9. Thus there is exactly one optimal feasible plan. Source counts, revision numbers, AND/OR rule cards, and plan utilities provide a deterministic ground truth. Every relevant authoritative revision is present in the permitted combined observations; there is no adversarially missing final update.

The following SHA-256 hashes were recorded before substantive model runs. Paths below are relative to `contributor-work/relayrepair/prototype/`.

| Asset | SHA-256 |
| --- | --- |
| `relayrepair.py` | `9cfd7531e3f4ec9db629af561a47efaf83ae01428a0e0502954e73f514494da5` |
| `test_relayrepair.py` | `bfbe25607e5d3cf6cadb424437dfa5ab2c72d5354f2a72d88b63d4aa21db2462` |
| `generated/pilot_manifest.json` | `b8365e5599ac546614ba7dc67b566b11442282b618c8402f9fa7be223f77c212` |
| `generated/model_observations.json` | `e2efd293324698390bba75991a0f584a417f6722c56460fef3688ad8700a70b0` |
| `generated/cases_with_oracle.json` | `ba577dd212b75f0d8f9613e119d45e0241de2bdd090258052f34637ce2f5b009` |
| `generated/scripted_results.json` | `e2a2ca5061ddcde3c9b0167af8fb8dfbe4d00f52bd879680d988f7cf2d475039` |

Before the first substantive inference, save a run manifest containing these hashes, the prompt-builder and adapter hashes, the protocol hash, the model settings, and a UTC start time. Hash all actual prompt files as they are constructed. Any later bug fix must produce a separately labeled protocol/run revision and retain the previous artifacts. Scores must never determine which cases are kept or replaced.

## Model and execution

All model calls request the locally configured identifier `gpt-6-astra` with reasoning effort `ultra`. This is a requested identifier, not an immutable server snapshot or independent verification of backend weights. Record the requested identifier and any actual server identity exposed by the CLI. Do not invent a version.

Use independent ephemeral Codex CLI calls in empty temporary working directories. No inherited conversation or implicit model history is shared between roles or rounds. Only explicitly constructed prompt content is passed. No shell, browser, applications, plugins, subagents, or other tool calls are allowed. Audit every emitted item lifecycle event; any non-message/non-reasoning item invalidates the call. Require exactly one completed turn and no error or failed-turn event.

The pilot is intentionally **tool-free**; the separate symbolic baselines can use code. The wrapper must explicitly override the generic scenario sentence allowing local code and the scenario's single-object output instruction. Actual model prompts must state the tool-free condition and the batched output schema clearly.

No arbitrary low output-token cap is imposed. The adapter's 480-second call timeout is an operational ceiling, not a claim of equal compute across conditions. Record actual usage and elapsed time. Workers, leaders, and centralized controls are not matched on total inference budget in this smoke test.

## Nine planned substantive calls

All 12 cases are batched together in each call; case order is fixed. There are three worker roles, reused through fresh calls in two rounds, and one leader role.

1. Three initial worker calls. Each sees public plan/rule semantics and only its own role's private cards for each case. Each returns a case-indexed message for the leader. It cannot inspect another worker's prompt or the oracle.
2. One initial leader call. It sees public cards and the three initial messages, then selects a plan for each case.
3. Three revision worker calls. Each sees the relevant final shuffled observation history for its own role, including authoritative revision numbers. It returns a new case-indexed message. Any explicit previous message supplied to a worker must be recorded in its prompt; there is no inherited state.
4. One final leader call. It receives the three new messages, followed by the older round-zero messages as delayed reports. Round identifiers are visible and truthful. It selects the final plan for each case. This is controlled stale-report replay, not a live asynchronous execution benchmark.
5. One centralized final control call. It receives the complete permitted final evidence history for every case, including revisions and old reports, with public rules and utilities. It does not see oracle answers or the team leader's choices.

The model-facing inputs must be assembled from `model_observations.json` only. Do not serialize `cases_with_oracle.json`, scripted answers, evaluator internals, local paths, credentials, or source-code locations into prompts. The evaluator loads oracle data only after responses are available.

Only explicit infrastructure fixes justify an additional call. Do not silently retry an incorrect answer, ask the same model for a better answer, or take best-of-N. Preserve the original failure, its cause, and the replacement call. Any repeated or amended run is labeled separately.

## Scoring

**Primary:** final leader optimal feasible-plan accuracy, expressed as `correct / 12` and a percentage. A case is correct exactly when the returned plan ID equals its deterministic final optimum. There are no ties in this version; future tied instances must accept every maximizer.

Also report:

- Initial leader accuracy, `correct / 12`.
- Centralized final accuracy, `correct / 12`.
- Final accuracy in each preregistered four-case stratum.
- The paired initial/final decisions, with whether the true optimum changed.
- Scripted baseline outcomes, explicitly labeled as programs rather than model measurements.
- Total calls, token usage where exposed, latency, schema errors, and infrastructure failures.

A missing case, unrecognized plan, malformed answer, or conflicting duplicate entries for one case is incorrect for that case. Do not repair substantive answers manually. Unknown case IDs do not replace missing requested cases. Preserve and flag identical duplicates even if they can be scored unambiguously. A failed call or prohibited tool event is invalid execution, not a reasoning error: report the planned 12-case denominator and missing results transparently and avoid producing a completed accuracy claim from an incomplete batch.

Do not combine initial correctness, final correctness, explanation quality, and multiple cases into an opaque near-zero headline score. Any strict both-round score is secondary and explicitly defined. Explanations are not graded by an LLM. This version does not claim to test semantic source-independence inference beyond its explicit source identifiers and rule structure.

The generic provenance-aware symbolic strategy is expected to solve all cases. If it does, describe this as a baseline and solvability check. Do not frame deliberately weak scripted strategies as scores from current AI models.

## Limitations fixed before results

- One requested model, one run, 12 small synthetic cases. No claim about “most models,” a frontier ranking, or population failure rates is supported.
- Batching creates shared-context correlation and possible cross-case learning. Twelve answers are not twelve independent model runs; a binomial confidence interval would overstate independence.
- The task uses explicit source IDs, numeric revisions, simple rules, a small finite action space, and randomized surface values. It may be solved perfectly by elementary symbolic state maintenance. That would limit research headroom.
- The centralized control gets raw evidence while the leader receives worker summaries, and total call budgets differ. Their difference is descriptive; it is not an isolated causal estimate of multi-agent benefit or cost efficiency.
- Replayed old messages are clearly tagged. This tests resistance to stale information under a controlled presentation, not realistic network fault tolerance or hidden teammate intentions.
- No arbitrary compression budget, code-generation task, model training, real scientific uncertainty, adversarial deception, or unrestricted autonomous research loop is evaluated here.
- The generator's other scripted conditions are not extra model runs. Distinguish executed model conditions from fixture/baseline checks.
- Model-serving software may change behind the requested identifier. Preserve timing, settings, input/output artifacts, and exact code versions without claiming immutable reproducibility.
- This smoke cannot establish the difficulty of the outer OpenRSI research task. A later outer-agent study must test whether protocol improvement remains challenging after supplying a competent baseline.

## Evidence handling and outcome reporting

Raw run files live outside the Git checkout under `research/relayrepair-pilot/`. Public artifacts are an explicit, manually reviewed allowlist: synthetic prompts, structured final responses, sanitized usage/settings metadata, manifest hashes, deterministic scores, and an explanatory report. Exclude local stderr, absolute personal paths, auth/config data, unreviewed raw event streams, internal thread identifiers, and reasoning events. Hashing a file does not make its contents safe to publish.

The report states what ran, what scored, what failed operationally, and what the result implies. If the model achieves 100%, say that this small version is too easy to support the requested challenging-eval claim. If it fails, show exact observable failure cases and compare with the centralized and symbolic controls before attributing a coordination weakness. Any harder follow-up is a new, separately registered experiment; it does not overwrite this result.

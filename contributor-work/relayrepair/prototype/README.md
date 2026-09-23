# RelayRepair: small executable prototype

This is an original, CPU-only, Python-standard-library prototype for testing evidence revision in three-agent teams. It is **not a submission-ready benchmark**. It contains no actual model measurements and no claim that current models struggle.

Run from this directory:

```sh
python3 relayrepair.py
python3 -m unittest -v
```

The generator fixes 12 pilot seeds before any model calls. Every case assigns private source and dependency-rule cards to three roles, with randomized IDs, ownership and unique plan utilities. Source cards state numeric criteria including negation (`must not exceed`); rule cards express AND/OR support. One honest source revision can invalidate a required support, preserve an alternative support, or change irrelevant evidence. Four of twelve revisions change the optimum. Every case has an always-valid, nonzero-utility fallback, which is generally suboptimal.

Four conditions are generated: initial; final with chronological revisions; final with shuffled delivery plus a deliberately late retransmission of an old card; and shuffled initial evidence without an update. The shuffled condition is a stress intervention, not a uniformly random permutation. Source revision numbers—not arrival order—determine truth. Repeated old cards are authentic stale observations, not fabricated or adversarial instructions.

`generated/model_observations.json` contains only text visible to the tested agents, including separated role views and the central/full-information control. `generated/cases_with_oracle.json` separately includes structured hidden truth for the evaluator. Never put the latter in model prompts. A real isolated evaluation must keep it out of worker-accessible storage. These local files are not a security boundary.

`generated/scripted_results.json` reports **SCRIPTED control scores, not LLM scores**:

- Latest-version symbolic: parses the same visible card strings as the models, then computes the best plan.
- Latest-arrival stale: incorrectly treats the most recently delivered source card as authoritative.
- Freeze-initial: ignores every revision.
- Abstain: supplies no plan and receives zero.

The intended exact-score denominator is 12 episodes per condition. Valid-plan rate and normalized achieved utility are supplementary diagnostics. A fallback selection can be valid while failing exact success. Score externally collected outputs with `python3 relayrepair.py --score answers.json`, where each record has `case_id`, `condition`, and `answer` (`{"plan_id": "P..."}`).

The symbolic control intentionally exposes the main limitation: these template-generated statements have a simple complete parser, so a code-enabled agent may solve the task immediately. A 100% scripted score proves evaluator feasibility, not research-task difficulty. Do not forbid a successful parser merely to lower model scores. A pilot must establish any communication or revision difficulty, and later benchmark design needs meaningful semantic variation or a research improvement objective beyond reconstructing this parser. The latest-version policy and evaluator share Boolean evaluation code; the independent check here is text parsing versus separate structured truth, not fully independent evaluator implementations.

Tests cover parser/oracle agreement, order and duplicate invariance, alternate support survival, a nonzero fallback when all sources fail, a mixture of changed/unchanged optima, stale-arrival behavior, abstention, and private-view partitioning. No external API calls, source downloads, or nonstandard dependencies are needed.

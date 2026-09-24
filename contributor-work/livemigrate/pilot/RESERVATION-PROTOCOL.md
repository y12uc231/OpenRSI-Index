# Separate-owner reservation pilot — declared before inference

This study extends the earlier two saturated LiveMigrate families with a third
semantic family. Its selection and complexity were informed by the earlier
successes; it is not an independently sampled test set. No reservation model
response was examined while building its contract, schedules or reference.

## Declared runs

Run every arm once, including successful, invalid and infrastructure outcomes:

| Run ID | Requested local model | Authoring mode | Policy |
| --- | --- | --- | --- |
| reservation-astra-centralized-001 | gpt-6-astra | Six sequential all-role revisions | Centralized control |
| reservation-astra-team-001 | gpt-6-astra | Two stages, each db → api → consumer | research/protocol-first.json |
| reservation-sol-team-001 | gpt-6-sol | Two stages, each db → api → consumer | research/protocol-first.json |

All calls request `ultra` reasoning. These are provider model aliases, not
immutable server snapshots. This is a small feasibility study, not evidence
about most models, a reliable model ranking or a causal teamwork advantage.
Centralized and team outputs have different schemas and realized token usage.
The sequential team policy gives later authors earlier implementations and
concrete interface messages; the deliberately weaker simultaneous policy is
not used as the only team baseline.

## Frozen input and execution

Before the first call, commit and archive the complete task, trusted evaluator,
transport, policy, positive/negative controls and this protocol. Record that
immutable Git revision, per-file source hashes and candidate hashes. Use the
archive for all three runs without task or oracle edits during the study.

The explicit worker packet contains the entire `API_CONTRACT.md`,
`PUBLIC_SCENARIO.json`, public immutable legacy helper, all current role source,
prior teammate messages and public-check feedback. All roles share the same
objective and information. Reference implementations, final causal schedules,
host oracle state and other agents' private reasoning are excluded.

Each arm makes exactly six tool-free coding calls, with no replacement
generations or selection among attempts. The controller performs a public check
after calls three and six; only the first can influence final code. Freeze the
final source hashes before running every held-out case. The workload is one
public schedule and all three held-out schedules in `families/reservation`.
They are correlated causal traces within one semantic task, not four independent
tasks. Publication makes the final schedules reproducible, not permanently secret.

Use host Python 3.12 with SQLite value limits and the pinned Python image from
`PROTOCOL.md`. Each logical service has its own isolated persistent database.
No candidate receives another service's store or the evaluator. Model calls
have no shell, browser, tools or arbitrary testing access. Conclusions therefore
concern this six-call interface, not full coding-agent capability.

Set `--inference-timeout 1200 --check-timeout 900` for all three arms. These
generous operational limits are fixed before inference; the public reference
already required about 60 seconds for 613 isolated callbacks. Record complete
final-source Docker reference measurements separately before launch. The
per-callback limit remains 30 seconds. Timeout and infrastructure outcomes are
unscored, never model failures. Runs may overlap; elapsed times then describe
observed local wall time and cannot establish comparative inference speed.

## Validity, reporting and decision rule

Publish all three outcomes and exact denominators. For each case retain overall
pass, static state, permanent trace violations, observed-history check,
completion, fault triggers and callback counts. Invalid code/protocol, callback
exceptions and work-bound violations are candidate-invalid and unscored.
Exhausted history/SQL oracle bounds are unscored. A complete execution with
semantic safety or progress violations is a scored failure. A history may be
incomplete because the program never answered; that is a visible progress failure,
not a claim that linearizability was exhaustively decided for a partial history.

Keep inference prompts, private reasoning, events and local metadata outside
public artifacts. Export aggregate usage and exact final source after checking
the exporter and source for sensitive paths/data. Count input plus output once;
cached input and reasoning are subsets. Verify source hashes against the frozen
commit, and final candidate hashes before publication. Preserve all earlier
amounts/identity successes alongside these results.

If all strong arms pass, report another saturation result. If there are failures,
inspect whether they are substantive atomicity, migration or recovery mistakes
versus ambiguous specifications, artificial role restrictions or harness errors.
Any critical evaluator defect invalidates the affected study: disclose it,
version the fix and declare a new study rather than retroactively changing scores.
No low score is required for publication of this instrument.

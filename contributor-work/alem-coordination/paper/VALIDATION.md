# What was checked

This record concerns the continuation study and its separately declared
diagnostic. Tests and independent reviews found no remaining blocking issue
within the checked scope. They do not prove that every possible bug is absent.

## Code and experiment identity

- Main protocol and execution code: local commit `9c8b632`, before the first
  new model call. All tracked inputs remained unchanged through completion.
- Additional diagnostic declaration: local commit `18a798c`, during the sixth
  coding call, after five development outcomes and before selection or any
  final evaluation. The declaration is not represented as part of the original
  protocol or as a public registry submission.
- Audited exporters and diagnostic runner: local commit `1d7fb51`, before the
  diagnostic started. They verify against the original fixed evaluator code.
- The study used the declared six responses exactly. No generated controller
  was manually repaired, and no final score was returned to the researcher.
- The first operator launch failed before any inference or game execution.
  Its records are retained separately; [the restart record](OPERATOR-ATTEMPTS.md)
  explains why it is one researcher study, not two attempts with one discarded.

## Real main-study results

The main public export passed its audit and a second independent offline check:

- Exact inventory and SHA-256 hashes of all 23 manifest-listed output files.
- All twelve unique evaluations: eight development checks with four worlds
  each, and four final checks with twenty worlds each.
- Every per-world score and aggregate metric, candidate identity, selection
  decision, paired difference and explicit reuse of the selected reference.
- Six response-bound candidate files and six usage records: 523,546 input and
  136,060 output tokens, totaling 659,606. Cached and reasoning tokens remain
  subsets. Model-call time totals 2,908.271 seconds.
- The exact JSON-only recomputation example from [REPRODUCE.md](REPRODUCE.md)
  ran successfully against the actual export. It makes no model or game calls.
- Both the scripted and independent checks reproduced all 40 earlier reference
  and original-Sol trajectories: trace hashes, reported reward and native
  diagnostic fields, and discrete costs. Time measurements may vary. See
  [the result](original-replay-check.json) and [the check](check_original_replay.py).

The main export contains 112 newly executed game trajectories. Its two
selected-reference final records reuse existing exact results; they do not add
another forty independent measurements. Memory and added-message interventions
were skipped by the protocol because pass-through won selection.

## Real diagnostic results

All twelve additional evaluations completed with 20/20 scored worlds each.
The diagnostic export passed its frozen audit and an independent offline review:

- Exact inventory and hashes of its twenty manifest-listed public files.
- All six candidate identities agree with the main study's model responses and
  development exports. The main selection remains the unchanged reference.
- All 352 world records across both studies agree with the combined analysis:
  eight programs, each on four development and forty final worlds.
- Every mean, paired count, reward component and action total in
  [RESULTS.md](RESULTS.md) and [study-analysis.json](study-analysis.json) agrees
  with the underlying public per-world records.
- All 4,449 protected file hashes match the diagnostic's final before/after
  record. Its declaration precedes selection and all main final starts.
- The tables preserve all six revisions. Call 3's recorded gain over the fresh
  reference is only 0.0000000745 percentage points; the report treats this as a
  numerical tie rather than evidence of improvement.

The diagnostic's monotonic elapsed timer records 1,646.246 seconds; evaluation
subprocesses total 1,616.029 seconds. Its calendar end-minus-start timestamps
give 1,767.858 seconds. These clocks differed, so the report calls the first
quantity **recorded elapsed runtime**, not wall-clock duration. Both original
timing records are retained; neither was silently corrected.

Both figures were rendered and visually inspected. Local documentation links
resolve. The shared world lists, complete results and observed ranking changes
are shown without selecting a retrospective new winner.

## What the automated checks cover

All **54 paper-directory tests passed** under host Python 3.12.14:

```sh
python3 -m unittest discover -s paper -p 'test_*.py'
```

The paper-directory tests cover resource and filesystem boundaries, exact
source and candidate identities, transfer-suite staging, timeouts, failed or
missing worlds, invalid submissions, selection and ties, token accounting,
declared interventions, response/code consistency, result reuse, private-data
exclusion, declaration timing, and stopping after infrastructure failure.

The separate diagnostic exporter was reviewed before execution. Its review
added checks that reconstruct counters from the actual twelve-field inventory,
reject results after a recorded stop, and revalidate declaration timing against
the main study's recorded container starts. These fixes preceded the diagnostic
run and did not change any controller or scoring rule.

## Limits of the checks

Real execution was on Linux ARM64 inside the recorded CPU container. We did
not validate x86 execution, independently rebuild a bit-identical public image,
or run the full OpenRSI twenty-four-hour research workflow. Mocked tests of
failure handling are not measurements of how often failures occur in deployment.

Successful source and result checks do not establish scientific novelty,
eliminate model nondeterminism, or turn one research trajectory into a reliable
model comparison. The [main report](README.md) and
[related-work review](RELATED-WORK.md) keep those conclusions separate.

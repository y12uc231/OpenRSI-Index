# Identity family: pre-inference study declaration

Date: 2026-09-23. This family was selected in the original `PROTOCOL.md` before
amount-family inference. Its contract, scenarios, reference, starter and oracle
were authored without inspecting model-generated amount-family solutions.

At this declaration, the amount family has finished: both team and centralized
diagnostic passed all three held-out traces. Those successes remain reported.
Identity cases are frozen in Git before identity inference. Neither outcomes nor
candidate source will be used to change these cases during this study.

Run exactly one team and one centralized diagnostic from the frozen source,
using the original protocol: requested `gpt-6-astra`, `ultra`, six calls, one
usable public feedback point, no tools or repository access, no replacement
generations. The only task change is `--task-root families/identity`. Source
hashes cover both the selected family and common execution machinery.

The complete workload is the one public and three held-out scenarios in this
family's `scenarios.py`. These are correlated traces of one semantic family.
Report every declared case, validity, completion, final-state correctness,
history correctness, actual usage, and infrastructure incidents. Six calls do
not match the arms' token budgets or adaptive depth; this remains a feasibility
diagnostic and cannot establish a causal teamwork effect.

Before inference, all 10 family unit checks pass. Independently executing the
reference through Docker passes all four cases and 162 callbacks. Four synthetic
bug controls can pass final-state checks while failing history. Alternate opaque
operation IDs and pointer events also pass, demonstrating the oracle does not
require the reference's internal representation. These are instrument checks,
not model results.

Archive the committed source into a fresh pilot directory. Keep raw prompts,
provider events and private reasoning outside public Git. Publish a sanitized
complete result after both runs finish, even if both pass everything.

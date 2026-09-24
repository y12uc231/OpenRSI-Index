# Local researcher feasibility pilot — declared before inference

This is a short code-generation research pilot, not a 24-hour OpenRSI trajectory,
not direct conversational game play, and not evidence about most models.

Run `gpt-6-astra` and `gpt-6-sol` once each through the existing local Codex
tool-free transport, requesting ultra reasoning. These are provider aliases;
no immutable model-server snapshot is exposed. Each arm receives three coding
calls, with no replacement generations or selection among separate runs. Each
response supplies a complete `controller.py`. After calls one and two, run all
four development worlds and return aggregate metrics plus bounded validity
diagnostics. After call three, freeze the artifact and evaluate all 20 fixed
worlds. Retain every arm, invalid artifact and infrastructure outcome.

The public packet contains the controller API, task design, official symbolic
renderer, action/block/item/specialization definitions, official game rules,
and exact upstream synchronization/handover/construction/communication code.
Packet files and hashes are recorded. It excludes evaluation trajectories,
per-world evaluation outcomes, private evaluator internals and other arms'
source or reasoning. Pass-through is the initial candidate. Each subsequent
call receives its own previous code and development feedback.

Before inference, freeze the runner and full selected public packet. Verify the
controller transport's pass-through parity and run the matched pass-through
baseline on the same evaluation protocol. Check every candidate's source hashes
before and after sandboxed execution. Generated code is never host-imported.

One model call has a generous 1,800-second operational deadline. One complete
development/evaluation invocation has a 10,800-second operator deadline (the
calling process allows 60 additional seconds for cleanup). Neither
is a claim about necessary compute; all actual time and tokens are reported.
No failure is inferred from infrastructure, timeout or quota exhaustion.
Candidate-invalid outcomes remain unscored under the main task's contract.
Research calls may overlap between arms, but full simulator evaluations use a
shared host lock and run serially to preserve the measured memory envelope.
Evaluation queue time is recorded separately from process execution time.

Primary endpoint: final mean normalized coordination reward and difference
from the fixed matched pass-through baseline. Secondary reports include base
and total reward, coordination subcategories, overrides, communication, survival,
invalid actions and resources. Do not choose a different endpoint after seeing
the results. Scores are reward fractions/percent, never binary pass rates.

The three-call interface tests an inexpensive initial research attempt. It
cannot establish full coding-agent capability, generation variance, performance
under unrestricted tools, a causal advantage of research teams, or the outcome
of a full 24-hour research budget. Any stronger claim needs separate evidence.
The final proposal can be scientifically valid without a poor LLM result.

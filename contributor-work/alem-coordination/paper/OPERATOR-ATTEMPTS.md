# Operator launch record

The six-call protocol and its code were committed locally before inference at
`9c8b632`. No files were published and no OpenRSI submission was made.

The first operator launch stopped during the initial reference check. The
filesystem sandbox denied access to the local Docker socket. Image inspection
failed before a container started. **Zero model calls and zero game worlds ran.**
The attempt's incomplete summary, staging manifest and operator record were
retained. It is an infrastructure failure, not a zero-reward controller result.

A separate read-only image inspection succeeded with the required local Docker
access. The operator then recorded a manual restart decision before launching
the unchanged study in a new directory. The original attempt was not overwritten.
No model response, candidate or world outcome was discarded or replaced. The
declared six-call budget, code, model, initial controller, world lists, selection
rule and final comparisons stayed the same. This was one manual infrastructure
restart before inference; the runner performed no automatic retries.

The second launch reproduced both starting controllers' original four-world
development histories exactly before beginning the first new model call.
Reference reward was 22.48427719%; original Sol reward was 19.81132142%.
Private directory names identify operator launches, not independent researcher
attempts. Both launches belong to one continuation study.

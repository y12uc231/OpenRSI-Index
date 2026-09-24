# Additional diagnostic: does the development ranking hold?

Declared on 24 September 2026 while the sixth coding call was running, after
seeing the first five development scores and before any final-suite results.
This is a separately declared secondary analysis, not part of the original
six-call protocol and not a replacement for its primary endpoint.

The first five new controllers have not exceeded the four-world development
reference. The original Sol controller previously ranked below that reference
on development but above it on the original evaluation worlds. We therefore
want to measure whether development selection misses useful controllers.

After the main study finishes and all six submitted source files are fixed,
evaluate **every new submission, calls 1–6**, on both the original 20-world
regression set and the 20-world transfer set. Use the same audited evaluator,
game, policy, resources, world lists and seeds. Make no additional model calls,
source repairs, selection changes or returns of final feedback to the model.
Reuse an existing final result only for exactly identical candidate bytes on
the same suite, and label the reuse. Preserve invalid/incomplete outcomes and
their costs; do not replace failures or average only successful worlds.

The primary result remains the development-selected controller's transfer gain
over pass-through. For this diagnostic, report a complete table of development,
regression and transfer scores for all six submissions, with paired world
differences from pass-through and the original Sol controller. Include all
regressions. Use descriptive statistics only; the six adaptive submissions are
not six independent researcher attempts.

If a rejected submission has a higher final-set mean, label it a retrospective
observation on that fixed set. Do not relabel it as the selected winner or claim
an independently validated best controller. Choosing code because of those
scores would require another untouched test set in a later study. Likewise,
this diagnostic cannot establish the expected value of iteration without
independent runs and a matched no-feedback search baseline.

This adds at most twelve CPU evaluations and zero inference calls. The extension
is motivated by development results, so it is not described as planned before
the six-call study began. Its declaration time and file hash are retained before
final outcomes become available.

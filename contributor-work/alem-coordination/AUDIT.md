# Pre-submission audit — 24 September 2026

The revised implementation is ready for proposal review with no known
submission-blocking defect after the fixes and checks below. This is a bounded
engineering and scientific review, not a guarantee that no undiscovered bug
exists or that OpenRSI will accept the task. The generated Harbor task and full
24-hour research trajectory remain downstream validation stages.

The audit started from personal-repository commit
`2a329a86ed391cd6f3478c8f3cba3e35c853888a`. Three independent reviews covered
runtime/scoring integrity, clean deployment, and experimental evidence; the
primary reviewer cross-checked the changes, official scoring source and
proposal requirements. Corrections are local pending the contributor's
submission decision. Nothing was posted upstream during this review.

## Defects found and corrected

| Finding | Correction and check |
| --- | --- |
| Shared `/tmp` imports could select an unverified `utils.py`; a sibling `controller/sandbox.py` could shadow the native helper. | Load task helpers from exact source bytes; use safe interpreter startup and fresh verifier-owned import roots containing verified upstream code. Regression fixtures reject both shadowing paths. |
| An unchecked, timestamp-valid Python bytecode cache could bypass source-only checks. | Compile the exact helper source bytes. A regression demonstrates ordinary cache acceptance and verifies that the hardened loader executes the verified source instead. |
| Fixed `/tmp/alem` staging prevented repeated evaluator invocations in one container. | Create and clean a unique private source directory per invocation. Unit checks cover cleanup; two complete evaluations now run consecutively in one ordinary container. |
| A confirmed controller exit after initialization was labeled as infrastructure failure. | Attribute observed post-ready EOF/broken-pipe exits to the candidate. Startup failures, unknown exits, other OS errors and timeouts remain infrastructure/incomplete. Both categories remain unscored. |
| The exporter could mark a study verified despite missing or invalid development evidence, and could overlook extra calls. | Require all declared call/check/candidate directories, exact candidate sources and valid development provenance. Retain known extra token usage while withholding a verified score and complete-accounting claim. Tests also preserve legitimate invalid development trials followed by a valid final candidate. |
| The published reproduction command omitted measured thread/cache settings and the process limit. | Align it with the measured CPU, memory, environment, process-limit and safe-startup settings. |
| A baseline test required bit-identical derived standard deviations across Python versions. | Keep mean/min/max and every archived per-world value exact. Allow only `1e-12` percentage-point rounding for SD/SE; check the added death diagnostic separately. The test passes under Python 3.9 and 3.12. No score or evidence file changed. |

The supervisor/probe use isolated Python startup. The engine and actors retain
the declared hash seed zero through explicitly sanitized environments and safe
import-path settings. Policy inference, recurrent-state updates, actions,
worlds, transition RNG, scoring and horizon are unchanged; the exact
[engine patch](native/ENGINE.patch) and regression checks establish that source
boundary.

## Verification

All **61 applicable offline tests pass** under Python 3.12.14: baseline 6,
controller 13, pilot 10, native 13 and exporter 19. One legacy Docker-specific
opt-in test is skipped; the actual single-container native kernel probe was
executed successfully. It checked private actor state, blocked communication
side channels, process restrictions, scratch limits and preserved hash seed.

The final runtime was copied into a minimal staging tree: exactly 291 upstream
source files, 20 checkpoint/config files, the declared runtime, task instructions
and submitted controllers. Git history, study evidence and result files were
excluded. Expected outcomes remained outside the container. The staged manifest
was checked before execution and unchanged afterward.

One network-disabled container then ran the reference followed by the unchanged
Sol final controller, with fresh output and actor state for each evaluation:

| Artifact | Valid worlds | Coordination reward | All original trajectory hashes | Full invocation time |
| --- | ---: | ---: | ---: | ---: |
| Pass-through reference | 20/20 | 18.52201324% | 20/20 exact | 125.29 s |
| Sol final | 20/20 | 19.46540922% | 20/20 exact | 128.68 s |

All native metrics, actions, override counts, episode lengths and completion
states also match. The entire sequence, including the kernel probe and container
startup, took **255.69 seconds** at **4 CPUs, 16 GiB and zero GPUs**. There were no
automatic retries, new model generations or controller changes. These are
deployment checks, not independent researcher-performance samples.

The [complete audit validation record](native/evidence/post-audit-validation.json)
contains every world, runtime/source hashes, comparison counts, resource limits
and test accounting. Older native artifacts remain unchanged with their original
source hashes; they are not relabeled as measurements of the corrected runtime.

The stricter exporter reproduces all original public Astra, Sol and scripted
control artifacts byte-for-byte. All six generated controllers, token totals,
world denominators and published scores are unchanged. Recomputed comparison
data and plot labels agree with the records.

## Scientific claims and submission boundary

The task is an automated researcher improving a frozen three-agent RL team.
The pilot is not conversational LLM game play, a full-budget research study,
a demonstration that most models fail, or a global novelty proof. Sol's positive
0.9434 percentage-point gain and its 8 improved / 5 tied / 7 regressed worlds
remain explicit. Survival and coordination effects have not been causally
separated. The almost-inactive scripted control cannot establish difficulty.

The primary sources were rechecked: [Alem](https://arxiv.org/abs/2606.08340),
[MATES](https://arxiv.org/abs/2609.26010),
[automated research-team comparisons](https://arxiv.org/abs/2603.29632), and
[OpenRSI contribution instructions](https://github.com/OpenRSI-Foundation/OpenRSI-Index/blob/main/CONTRIBUTING.md).
The [prior-art assessment](NOVELTY.md) remains deliberately limited to this
specific research-task implementation. The work is grounded in those external
sources, not in the contributor's older projects.

Before posting, the rendered proposal needs its contribution commit updated to
the reviewed revision and its native command updated to `python -I -B`.
Its existing historical runtime figures remain genuine measurements; the fresh
audit timings above should be cited separately. These are implementation and
evidence corrections, with no change to the scientific task or score.

Residual limitations: fixed public worlds; one checkpoint/training seed; one
three-call attempt per requested provider alias; arm64 execution measured, not
x86_64; no full Harbor/24-hour validation yet; inherited Work-snapshot interpreter
and library trust; no proof against arbitrary malicious code or hardware timing
side channels. The optional Qwen serving lane still has no GPU/inference run.

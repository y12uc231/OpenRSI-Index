# Pre-submission audit — 24 September 2026

The revised implementation is ready for proposal review. After the fixes and
checks below, we know of no defect that blocks submission. This review cannot
guarantee that the software has no undiscovered bugs or that OpenRSI will accept
the task. The generated Harbor task and the full 24-hour research run still
need validation in the target infrastructure.

The audit started from personal-repository commit
`2a329a86ed391cd6f3478c8f3cba3e35c853888a`. Three independent reviews checked
runtime and scoring integrity, deployment in a clean environment, and the
experimental evidence. The primary reviewer cross-checked the changes, official
scoring source and proposal requirements. The corrections remain local pending
the contributor's submission decision. Nothing was posted upstream during this
review.

## Problems found and fixed

| Problem | Fix and evidence |
| --- | --- |
| Python could load an unverified `utils.py` from shared `/tmp`, or a `controller/sandbox.py` instead of the intended native helper. | Load task helpers from their exact source bytes. Use safe Python startup and fresh private directories containing verified upstream code. Tests cover both wrong-file paths. |
| A cached compiled Python file could bypass source checks if its timestamp appeared valid. | Compile the exact helper source bytes. A test first demonstrates that the ordinary loader accepts such a cache, then checks that the corrected loader uses the verified source. |
| Preparing code at the fixed path `/tmp/alem` prevented repeated evaluations in one container. | Create and clean a unique private source directory for each invocation. Tests check cleanup; two full evaluations now run consecutively in one ordinary container. |
| A confirmed controller exit after initialization was reported as an infrastructure failure. | If a ready controller has exited and its pipe closes or breaks, attribute that failure to the submitted controller. Startup failures, unknown exits, other operating-system errors and timeouts remain infrastructure/incomplete. Both categories stay unscored. |
| The exporter could approve a study with missing or invalid development evidence, or overlook extra model calls. | Require all declared call, check and candidate directories; exact candidate source; and valid development provenance—the record of code, data and runtime used. Count known extra token usage, but withhold a verified score and a complete-accounting claim. Tests also preserve legitimate invalid development trials followed by a valid final submission. |
| The reproduction command omitted the measured thread/cache settings and process limit. | Match the command to the measured CPU, memory, environment, process-limit and safe-startup settings. |
| A baseline test required derived standard deviations to match bit-for-bit across Python versions. | Keep the mean, minimum, maximum and every archived per-world value exact. Allow only `1e-12` percentage-point rounding for standard deviation (SD) and standard error (SE). Check the added death diagnostic separately. The test passes on Python 3.9 and 3.12. No score or evidence file changed. |

The supervisor and diagnostic probe use isolated Python startup. The game
engine and agents use explicitly controlled environments and safe import
settings while retaining the declared Python hash seed of zero. This prevents
the import problems above without changing the intended hash behavior.

The policy's predictions, its recurrent memory updates, action handling, worlds,
random-number generation, scoring and maximum episode length are unchanged.
The exact [engine patch](native/ENGINE.patch) and regression tests show the
limits of the source changes.

## Checks completed

All **61 applicable offline tests pass** on Python 3.12.14:

| Test group | Passed |
| --- | ---: |
| Baseline | 6 |
| Controller | 13 |
| Researcher pilot | 10 |
| Native single-container runtime | 13 |
| Results exporter | 19 |
| **Total** | **61** |

One older Docker-specific opt-in test was skipped. The actual operating-system
isolation probe for the single-container runtime passed. It checked private
agent state, the tested restrictions on communication outside the game,
process restrictions, scratch-file limits and the preserved hash seed.

The final runtime was copied into a minimal staging tree: exactly 291 upstream
source files, 20 checkpoint/configuration files, the declared runtime, task
instructions and submitted controllers. Git history, study evidence and result
files were excluded. Expected results stayed outside the container. The staged
file manifest—a list of files and their checksums—was checked before execution
and was unchanged afterward.

One container with networking disabled then ran pass-through followed by the
unchanged Sol final controller. Each evaluation started with fresh output and
agent state. Pass-through is the baseline that accepts every action proposed by
the fixed policy.

| Controller | Valid worlds | Coordination reward | Exact matches to original trajectory checksums | Full invocation time |
| --- | ---: | ---: | ---: | ---: |
| Pass-through reference | 20/20 | 18.52201324% | 20/20 | 125.29 s |
| Sol final | 20/20 | 19.46540922% | 20/20 | 128.68 s |

A trajectory checksum summarizes the saved sequence of game states, internal
states and actions. All native metrics, actions, counts of changed actions,
episode lengths and completion states also match. Coordination percentages are
reward values, not pass rates.

The whole sequence, including the isolation probe and container startup, took
**255.69 seconds** with **4 CPUs, 16 GiB of memory and zero GPUs**. There were no
automatic retries, new model generations or controller changes. These runs
check deployment correctness; they are not new independent measurements of
researcher performance.

The [complete audit validation record](native/evidence/post-audit-validation.json)
contains every world, runtime and source checksums, comparison counts, resource
limits and test counts. Older native artifacts remain unchanged with their
original source checksums. They are not relabeled as measurements of the
corrected runtime.

The stricter exporter recreates all original public Astra, Sol and scripted
control artifacts byte-for-byte. All six generated controllers, token totals,
world counts and published scores are unchanged. Recomputed comparison data
and plot labels agree with the records.

## What the evidence supports

The task asks an automated researcher to improve a fixed three-agent
reinforcement learning (RL) team. The trained game policies remain fixed; the
researcher writes a controller around them. This pilot is not conversational
language-model game play or a full-budget research study. It does not show that
most models fail, or prove that no similar task exists anywhere.

Sol's positive **0.9434 percentage-point** gain remains explicit: **8 worlds
improved, 5 tied and 7 regressed**. We have not separated the effects of longer
survival from better coordination. The scripted comparison controller changed
very few actions, so it cannot establish task difficulty.

The primary sources were rechecked: [Alem](https://arxiv.org/abs/2606.08340),
[MATES](https://arxiv.org/abs/2609.26010),
[automated research-team comparisons](https://arxiv.org/abs/2603.29632), and
[OpenRSI contribution instructions](https://github.com/OpenRSI-Foundation/OpenRSI-Index/blob/main/CONTRIBUTING.md).
The [prior-art assessment](NOVELTY.md) makes a limited claim about this specific
research-task implementation.

## What remains before and after submission

The revised proposal wording uses the audited implementation and the corrected
`python -I -B` command. Before posting, publish the reviewed revision through the
personal repository and check that the proposal points to that exact commit.
Earlier runtime figures remain genuine measurements; the new audit timings are
reported separately. These corrections change the implementation and evidence
checks, not the scientific task or score.

The remaining limits are:

- **Research scope:** fixed public worlds, one trained checkpoint and training
  seed, and one three-call attempt per requested provider model alias.
- **Deployment coverage:** execution was measured on arm64, not x86_64. The
  complete Harbor task and 24-hour research run have not been validated.
- **Trust boundary:** Judge inherits the Work snapshot, including its Python
  interpreter and libraries. Those inherited files remain a trust limitation.
  The isolation checks do not prove protection against all malicious code or
  hardware timing side channels.
- **Optional Qwen comparison:** preparation exists, but no GPU or Qwen inference
  run has taken place.

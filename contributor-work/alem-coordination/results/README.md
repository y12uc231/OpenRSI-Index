# Researcher pilot: complete results

Two short research attempts produced one unchanged baseline and one modest
improvement. GPT-6 Astra finished at **18.5220%** coordination reward. GPT-6 Sol
finished at **19.4654%**, an improvement of **0.9434 percentage points** over the
matched baseline. Both final controllers completed all 20 required game worlds.
These percentages measure reward relative to the game's coordination maximum;
they are **not pass rates**.

The language models wrote Python controllers for an existing three-agent
reinforcement learning (RL) team. RL agents learn from rewards. Here, their
trained policy—the model that proposes each game action—was fixed. The new
controllers could keep or change those proposed actions. The language models
did not play the game through conversation. This contribution is a runnable
OpenRSI research task on Alem; the [prior-art audit](../NOVELTY.md) explains its
relationship to earlier work.

![Every final world and its paired reward difference](pilot.svg)

## What each researcher was allowed to do

The task, assets, baseline, prompt construction and three-call study plan were
fixed before any researcher model ran, at commit
[`d4bdd34f4170d2e61f24527d7ed68b3ad0866492`](https://github.com/y12uc231/OpenRSI-Index/tree/d4bdd34f4170d2e61f24527d7ed68b3ad0866492/contributor-work/alem-coordination).
Each requested model name received one attempt: three coding responses, no tool
access, and `ultra` reasoning effort. After each of the first two submissions,
the researcher received summary feedback from four development worlds. The
third submission was evaluated once on twenty fixed evaluation worlds.

There were no replacement generations, repair calls, discarded failures or
selection of the best result from multiple attempts. This was a short test of
controller development, not the proposed 24-hour research run with tools.

The **pass-through baseline** always accepts the fixed policy's proposed action.
The scripted control is a comparison controller written by the assistant during
task construction.

| Controller | Development submission 1 | Development submission 2 | Final 20-world reward | Final change from baseline |
| --- | ---: | ---: | ---: | ---: |
| Matched pass-through | 22.4843% reference | 22.4843% reference | 18.5220% | 0 percentage points |
| Scripted visible-sync control | Not run | Not run | 18.5849% | +0.0629 percentage points |
| GPT-6 Astra | 15.8805% | 22.4843% | 18.5220% | 0 percentage points |
| GPT-6 Sol | 17.7673% | 19.8113% | 19.4654% | +0.9434 percentage points |

The development baseline was measured once; the table repeats it only to make
comparison easier. Development and evaluation use different worlds, so their
scores do not form one directly comparable learning curve. The initial research
packet included the evaluation baseline's summary score. Astra used its second
submission to measure pass-through on the development worlds.

Both researchers' first submissions scored below the development baseline.
Astra first tried directional invitations and a local readiness quorum—a check
that enough nearby agents were ready—for synchronized resource collection. It
then checked and retained pass-through. Keeping the stronger baseline was a
valid conservative decision. Its final controller reproduces every baseline
trajectory, or sequence of game states and actions, and every metric exactly.

Sol first combined handover priority, local assignments of positions to agents,
and a quorum using the game's built-in messages. It revised the controller to
use bounded path searches, exact quorum sizes, target-readiness checks and tool
checks. Its final source is byte-for-byte identical to its second generation.
Its SHA-256 file checksum is
`3862d57dbf57dbb8e1f2efff6cd32a345dd7006a0dab58d40b45e0ff5ae38d89`.
On evaluation, it improved 8 worlds, tied 5 and regressed on 7. It changed
1,009 of 28,713 proposed agent actions (3.51%).

The scripted control's machine-readable label, `author-written heuristic`,
refers to the assistant-written rule-based controller. It is not an independent
human result or a researcher-model result. It changed only nine actions and
changed two world scores in opposite directions. Such an inactive control
cannot establish how difficult the task is.

## What changed in the game

The table retains Alem's reward categories. A joint environment step updates the
game using the team's actions; an alive-agent step counts one living agent for
one step. Communication actions are the game's built-in way for agents to send
messages.

| Final metric | Pass-through | Sol |
| --- | ---: | ---: |
| Coordination reward | 18.5220% | 19.4654% |
| Base reward | 14.2627% | 14.4931% |
| Total reward | 16.0638% | 16.5957% |
| Soft coordination reward | 21.2500% | 23.2500% |
| Hard-sync coordination reward | 14.1477% | 14.9432% |
| Handover coordination reward | 85% | 85% |
| Construction coordination reward | 0% | 0% |
| Joint environment steps, total | 8,489 | 9,571 |
| Alive-agent steps, mean per world | 1,064.05 | 1,117.25 |
| Synchronization attempts, mean per world | 10.45 | 14.80 |
| Synchronization successes, mean per world | 4.65 | 5.25 |
| Native communication actions, total | 386 | 872 |

Survival and synchronization both changed. More synchronization successes do
not prove greater efficiency: the mean success rate per episode fell from
0.5695 to 0.4621. No controlled comparison has removed individual controller
components to identify which change caused the gain. Construction was never
attempted, so zero construction reward does not show an inability to use
construction opportunities.

We also have not shown that the trained base policy is essential. That would
require comparisons with a controller acting alone and with the policy's
action scores, or logits, withheld.

## Model usage and elapsed time

| Researcher | Accepted coding responses | Input tokens | Output tokens, including reasoning | Total tokens | Whole research attempt |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-6 Astra | 3 | 176,289 | 21,594 | 197,883 | 1,292.34 s |
| GPT-6 Sol | 3 | 277,470 | 67,703 | 345,173 | 2,590.41 s |

The following counts are **already included** in those totals. Adding them
again would double-count usage.

| Included subset | GPT-6 Astra | GPT-6 Sol |
| --- | ---: | ---: |
| Cached input tokens | 70,400 | 145,024 |
| Reasoning output tokens | 17,649 | 51,624 |

Three calls means three accepted coding responses from the command-line client
(CLI). Internal service call counts are not exposed. The model names are the
requested provider aliases; immutable server-model identifiers were not
available. The two attempts did not have matched token budgets.

Researcher calls overlapped. Simulator checks shared a lock, so only one check
could run at a time. The elapsed times include waiting: they must not be added
to calculate the study's elapsed time or used to rank model speed. The original
final Docker evaluations took 277.79 s for Astra and 310.75 s for Sol. The game
agents used no language-model inference or training.

## How the exported results were checked

The independent exporter is the script that checks the original records and
writes the public results. It verifies the fixed commit, source checksums,
research packet, baseline, exact submitted code, source and checkpoint (saved
policy weights) file lists, runtime images, every required outcome, and reward
averages. It keeps invalid, infrastructure-failed and incomplete outcomes as
unscored. It never
turns them into zero rewards or drops their worlds.

All nineteen offline exporter tests pass. The final audit added tests for
missing development results, invalid development provenance, extra calls and
their token usage, missing candidate source, and inconsistent reported token
totals. Provenance means the records showing which code, data and runtime were
used. Re-exporting the original three arms—Astra, Sol and the scripted
control—with the stricter checks produces byte-identical public artifacts.

## Running inside one container

The original study used separate Docker containers for the game agents. The
submission route uses three private agent processes inside one ordinary Linux
container. It needs neither Docker inside Docker nor access to the host's
Docker socket.

The original deployment checks reproduced the submitted controllers' saved
results as follows:

| Controller | Exact matches to original worlds | Elapsed time |
| --- | ---: | ---: |
| Unchanged pass-through | 20/20 complete game-state, internal-state and action trace checksums; rewards and episode lengths | 145.39 s |
| Unchanged Sol final | 20/20 traces, rewards and action counts | 130.38 s |

Both checks used four CPUs, a 16 GiB memory cap and zero GPUs. These are checks
that the software runs correctly in another deployment, not new researcher
attempts or independent performance samples. All integration failures and the
earlier one-world trace mismatch remain in the
[deployment ledger](../native/evidence/README.md).

The final route permits one fixed private scratch file instead of a general
writable temporary directory. We do not claim that every possible controller
behaves identically across the two deployments. Kernel execution on x86_64 has
not been validated. Full validation in Harbor and RSI-Harness, the target task
and research-run infrastructure, remains a later stage.

A later [pre-submission audit](../AUDIT.md) corrected which source files the
runtime could import and how it prepared files for repeated runs. The corrected
runtime ran both complete 20-world evaluations consecutively in one minimal
container: pass-through took 125.29 s and unchanged Sol took 128.68 s. All 40
traces and all metrics matched exactly. These checks leave the original
researcher records unchanged; see the
[separate audit evidence](../native/evidence/post-audit-validation.json).

## Qwen preparation: no inference run yet

The [compatible endpoint adapter and pinned Qwen configuration](../pilot/OTHER-MODELS.md)
are prepared. An adapter connects the researcher runner to a model-serving
endpoint. A later [CPU-only tokenizer check](qwen-tokenizer-planning.json)
counted all six observed prompts using the fixed Qwen3.8-27B tokenizer and its
chat template, which formats messages for the model.

Those prompts occupy 25,980–30,564 tokens. Each fits a 65,536-token context while
reserving the full 32,768 tokens for a completion; the smallest remaining margin
is 2,204 tokens. This updates the archived pre-pilot planning status without
changing the fixed research packet.

No Qwen weights, GPU, serving endpoint or inference run was used. Checks against
a live vLLM model server and actual resource measurements remain unvalidated.
Future prompts that are too long must be rejected, not silently shortened. The
optional serving estimate is one H100 80 GB, 16 CPU cores and 128 GiB RAM. The
evaluation task itself needs no GPU. Paid-provider adapters are not implemented.

## Evidence and reproduction

- [Comparison data](comparison.json): every final world, all generation scores,
  usage and behavioral diagnostics.
- [Astra](astra-001/summary.json), [Sol](sol-001/summary.json) and
  [scripted control](visible-sync-001/summary.json): checked summaries; each
  directory preserves exact code, final outcomes and a manifest listing files
  and their checksums.
- [Safe exporter](export_alem_researcher.py),
  [control exporter](export_alem_control.py),
  [comparison builder](compare_alem_researcher.py) and
  [tests](test_export_alem_researcher.py).
- [Plot script](plot_alem_pilot.py) and
  [offline tokenizer planning script](check_alem_tokenizer.py).
- [Native entrypoint and isolation contract](../native/README.md),
  [development protocol](../pilot/PROTOCOL.md) and
  [fixed baseline](../controller/evidence/evaluation-baseline.json).

From this results directory, rebuild the plot with Matplotlib 3.10.3 and run the
exporter tests:

```sh
python plot_alem_pilot.py \
  --baseline ../controller/evidence/evaluation-baseline.json \
  --results . --output /tmp/alem-pilot-figure
python -m unittest test_export_alem_researcher -v
```

The twenty plotted dots are outcomes from fixed worlds. They are not twenty
independent research attempts or an uncertainty interval. This study uses
public seeds, one checkpoint, one attempt per requested model alias and three
calls without tools. It does not establish broad model rankings, performance
on unseen worlds, or difficulty under the full research budget. Sol's positive
result is retained. There is no evidence here that most models fail this task.

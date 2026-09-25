# Alem Coordination Lab

**Submitted:** [OpenRSI Task Ideas Discussion #132](https://github.com/OpenRSI-Foundation/OpenRSI-Index/discussions/132),
using the personal account `y12uc231`. See the [submission record](SUBMISSION.md).
The completed
[Sol continuation study](paper/README.md) reports six additional coding calls,
new-world evaluation and a literature review. Its results support a task
proposal; they do not yet establish a strong independent-paper claim. The
original pilot below remains a separate, unchanged result.

**Can a language model write code that helps three pretrained game agents work
better together?** This task tests that question in
[Alem](https://github.com/alem-world/alem-env), an existing game environment with
shared tasks such as synchronized actions, item handovers and construction.

The researcher writes a Python controller, tests it, reads the results and
revises the code. The three game agents were trained with reinforcement learning
(RL): they learned how to act from rewards. Their trained model stays fixed.
The controller can change their decisions without retraining them.

Alem and methods for improving a fixed policy already exist. Our contribution
is this runnable OpenRSI research task, its evaluation rules and its evidence.
See [related work and what is new](NOVELTY.md).

## What the researcher builds

The submission is one `controller.py` file, used by all three game agents.
Each agent runs its own copy with private memory. At each step, the controller
receives that agent's game observation, available actions, the trained model's
suggested action and action scores, and its own previous reward. It returns an
action and updated memory. It may choose any legal action.

For example, a controller could remember a meeting location or wait until
teammates are ready for a shared action. It can coordinate through ordinary
game actions and the game's four communication actions. A communication action
uses a turn. Information about teammates that the game normally reveals stays
available; the controller cannot read their private inputs or the simulator's
hidden state.

The language model is the researcher that writes this code. The game agents
are trained RL models, not language models chatting with one another. Each pilot
trial below used a single model as the researcher. Comparing it with a team
of researchers would require a separate study with equal research budgets.

The [task design](TASK_DESIGN.md) and [controller interface](controller/CONTRACT.md)
give the exact rules. These documents were part of the original pilot and remain
unchanged so that its instructions can be checked against its results.

## How the score works

Every submitted controller is tested on the same 20 public game worlds.
Four separate worlds are available for development. The main score is Alem's
coordination reward, averaged across all 20 evaluation worlds. Higher is better.
A score of 18.52% means 18.52% of the game's coordination reward maximum; it does
not mean the controller passed 18.52% of the worlds.

The reference controller always accepts the trained model's suggested action.
It scored **18.5220%**. A new controller's improvement is measured against that
reference under the same evaluation rules. Deaths and zero rewards count in
the average. Invalid code, timeouts and incomplete evaluations receive no score;
their records are kept.

The world seeds and simulator are public. These results measure improvement on
a fixed workload. They do not show performance on secret or previously unseen
worlds.

## What the pilot found

Each researcher had three code-writing calls. The first two versions were tested
on the four development worlds; the third was tested on all 20 evaluation worlds.
All six code responses and their results were kept.

| Controller | Coordination reward | Gain over reference |
| --- | ---: | ---: |
| Reference: keep the trained model's action | 18.5220% | — |
| GPT-6 Astra's final controller | 18.5220% | 0 percentage points |
| GPT-6 Sol's final controller | 19.4654% | +0.9434 percentage points |

Astra tried a change that lowered development reward, then returned to the
reference. Sol improved eight evaluation worlds, tied five and worsened seven.
These were short trials without tool access during code generation. They do
not show that most models fail, establish a model ranking, or replace the
proposed 24-hour research run. The [full results](results/README.md) include
all attempts, code, token usage, game behavior and limitations.

## What runs today

The evaluator runs on CPUs. No GPU or model training is needed.

| Part | Where to find it |
| --- | --- |
| Download the public source and saved model weights; build the CPU environment | [Baseline setup](baseline/README.md) |
| Run the evaluator and three private controller processes in one container | [Current execution guide](native/README.md) |
| Inspect the reference controller | [Reference code](controller/reference/controller.py) |
| Read the short researcher-pilot rules | [Pilot protocol](pilot/PROTOCOL.md) |
| Inspect the simple scripted comparison controller | [Scripted control](controls/README.md) |
| Prepare an optional open-model comparison | [Other-model setup](pilot/OTHER-MODELS.md) |

The original pilot used a separate container for each controller process.
The current evaluator uses one ordinary container and needs no nested Docker,
Docker socket or added capabilities. A [pre-submission audit](AUDIT.md) fixed
import isolation, repeat-run and evidence-checking bugs. **61 applicable tests
passed.** A fresh run of the reference and unchanged Sol controller reproduced
**all 40 original world histories exactly**, including game state, hidden state
and actions. Both evaluations plus the isolation probe took **255.69 seconds**
on four CPUs with 16 GiB RAM. See the [audit evidence](native/evidence/post-audit-validation.json).

Earlier checks are retained with their original timings: the reference took
278.79 seconds in the separate-container setup and 145.39 seconds in an earlier
single-container check; the first Sol replay took 130.38 seconds. The
[deployment record](native/evidence/README.md) also keeps failed integration
attempts. A separate [863-step comparison](controller/prototype-parity.json)
checked that passing observations and actions between processes preserved the
game's behavior. These checks validate execution; they are not new model trials.

The upstream evaluator also produced a separate **18.9308%** reference result.
It carries random-number state between worlds. Our controller evaluator resets
that state for each world, so **18.5220% is the correct comparison for this task**.
The [baseline guide](baseline/README.md) explains the difference. A low reference
reward alone does not prove that the research task is difficult.

## Reproduce the single-container evaluation

From this directory, use host Python 3.11+, Git and Docker on one machine:

```sh
python3 baseline/acquire.py
python3 baseline/build.py
alem_image_id=$(docker image inspect --format '{{.Id}}' openrsi-alem-native20:portable)
alem_task_dir="$PWD"
mkdir -p baseline/.work/results/native-reference-001
docker run --rm --network none --cpus 4 --memory 16g --pids-limit 256 \
  --cap-drop NET_RAW --user 0 \
  --env PYTHONHASHSEED=0 --env PYTHONDONTWRITEBYTECODE=1 \
  --env JAX_PLATFORM_NAME=cpu --env WANDB_MODE=disabled \
  --env MPLCONFIGDIR=/tmp/matplotlib --env XDG_CACHE_HOME=/tmp/cache \
  --env OMP_NUM_THREADS=4 \
  --mount "type=bind,src=$alem_task_dir/baseline/.work/source,dst=/app,readonly" \
  --mount "type=bind,src=$alem_task_dir/baseline/.work/assets,dst=/assets,readonly" \
  --mount "type=bind,src=$alem_task_dir,dst=/task,readonly" \
  --mount "type=bind,src=$alem_task_dir/baseline/.work/results/native-reference-001,dst=/results" \
  "$alem_image_id" python -I -B /task/native/run.py \
  --candidate /task/controller/reference --suite evaluation --output /results
```

Use a new output directory for every attempt. For a submitted controller,
replace `--candidate` with its directory containing `controller.py`. Use
`--suite dev` for the four development worlds. The environment and candidates
have no network during execution. `result.json` contains the full operator
record; only the summary in `feedback.json` is returned to the researcher after
an evaluation. This local validation command mounts the checkout for convenience.
In OpenRSI, **Work** is the researcher's working environment and **Judge** is the
evaluation phase. Their images must use the [minimal content allowlist](native/README.md#minimal-base--judge-content-allowlist),
excluding evidence, results and repository history. A submitted candidate must
be available inside the container; mount its directory read-only at `/candidate`
and pass `--candidate /candidate`.

Allow **eight CPU cores and 16 GiB RAM on one machine** for research and evaluation;
zero GPUs. The measured native pass-through used a four-CPU container cap.
The evaluator allows up to 10,800 seconds per candidate so that longer-lived
teams can reach the game's 10,000-step limit. An incomplete run has no score.

The portable build and native baseline are verified on Linux/arm64.
Each result records the container image used. Other architectures and rebuilt
images still need execution checks. The code and short pilot are ready for
proposal review. Packaging as a Harbor task and a full run in RSI-Harness,
OpenRSI's research runner, remain to be validated.

## Checks

```sh
python3 -m unittest discover -s baseline/tests -v
python3 -m unittest discover -s controller -p 'test_*.py' -v
python3 -m unittest discover -s pilot -p 'test_*.py' -v
python3 -m unittest discover -s native -p 'test_*.py' -v
ALEM_EXPORT_REPO="$PWD/../.." python3 results/test_export_alem_researcher.py
```

These instructions are written for Python 3.11 or later. The audit ran the test
suites with Python 3.12.14. One older, optional Docker test was skipped; the
current evaluator's isolation probe was run successfully.

Judge evaluates the complete saved Work environment. Checks protect task files
and isolate controller processes, but cannot independently establish trust in
the inherited Python interpreter and libraries. The [execution guide](native/README.md) explains this
limit and the difference in temporary-file support between the two setups.
The optional Qwen comparison has only been prepared; no Qwen inference or GPU
run has been performed.

# Alem Coordination Lab

A CPU-only automated-research task: improve a pretrained three-agent team's
coordination by writing and testing decentralized controller code. The inner
agents are frozen recurrent RL policies. An LLM researcher develops the
controller through repeated code → experiment → feedback → revision cycles.

This is a new OpenRSI task implementation on the existing
[Alem environment](https://github.com/alem-world/alem-env), not a new game or a
claim that frozen-policy adaptation was invented here. See the
[scientific design](TASK_DESIGN.md) and [prior-art audit](NOVELTY.md).

Each game actor receives only its own official observation, legal-action mask,
frozen policy proposal/logits and private memory. The game already exposes some
teammate information; it remains available. Ordinary game actions and four
native communication actions are the only ways to coordinate. Controllers may
choose any legal action. They cannot inspect the simulator state or pool their
observations through a side channel.

## What is implemented

- [Public source/checkpoint acquisition and CPU build](baseline/README.md),
  with immutable upstream revisions, 291 source-file hashes, 20 asset hashes
  and a dependency lock. No training or GPU is required for evaluation.
- [Candidate-only evaluator](controller/CONTRACT.md), with one trusted simulator
  and three separate controller containers, recreated for every world.
- [Validated single-container deployment](native/README.md), with three private
  actor processes and no Docker socket, nested containers, or extra capabilities.
- [Pass-through baseline](controller/reference/controller.py), exact native
  metrics, fixed development/evaluation worlds, complete outcome retention,
  source/asset/candidate provenance checks and aggregate feedback.
- [863-step transport parity evidence](controller/prototype-parity.json),
  including earlier harness errors, plus Docker isolation checks.
- [Three-call local researcher pilot](pilot/PROTOCOL.md) and a separately
  [prepared open-model transport](pilot/OTHER-MODELS.md).
- [Simple scripted synchronization control](controls/README.md), kept distinct
  from model-generated results.

The matched isolated controller baseline achieved **18.52% normalized
coordination reward** across all 20 evaluation worlds in **278.79 seconds**,
with zero overrides and verified provenance. This is the baseline for controller
improvement. It is not an LLM score or a task success rate.

The original native deployment reproduced **all 20 complete state/action/latent
trace hashes**, every reward and every episode length in **145.39 seconds** on
four CPUs with a 16 GiB memory cap. This establishes a concrete execution route
for the current single-container Harness. See [all deployment attempts and
limits](native/evidence/README.md). The researcher pilot retains its original
Docker deployment identity; general temporary-file behavior differs between
the two routes.

The native unchanged policy separately achieved **18.93% normalized coordination reward**
over all 20 native evaluation worlds. That separate run uses the upstream
continuous transition RNG. The controller track has explicit per-world RNG and
uses the matched baseline above; never substitute the native score into a
controller improvement claim. See [all native metrics and caveats](baseline/README.md).
Low starting reward does not establish frontier researcher failure.

The completed [researcher pilot](results/README.md) retained all six coding
responses and every measured outcome. With one three-call attempt each,
GPT-6 Astra retained the baseline at **18.52%**, while GPT-6 Sol achieved
**19.47%**, a **0.94 percentage-point gain**. Sol improved eight worlds, tied
five and regressed on seven. Its unchanged controller also reproduced all
20 original traces on the single-container route in **130.38 seconds**.
These short tool-free attempts do not establish full-budget research
difficulty or a general model ranking. The results directory includes exact
generated code, costs, per-world data, and later CPU-only planning evidence
for the prepared Qwen comparison lane; no Qwen inference was performed.

The subsequent [pre-submission audit](AUDIT.md) fixed evaluator import isolation,
repeat-run staging and evidence-accounting defects. The corrected runtime
passed a fresh kernel probe and reproduced **all 40 original trajectories**
for reference and Sol, run consecutively in one container in **255.69 seconds**.
All 61 applicable offline checks pass. The original pilot and historical
measurements remain unchanged.

## Reproduce the single-container evaluation

From this directory, with host Python 3.11+, Git, Docker and one CPU node:

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
record; only `feedback.json` is returned to a researcher during iteration.
This local validation command mounts the checkout for convenience. Generated
Work/Judge images must use the [minimal content allowlist](native/README.md#minimal-base--judge-content-allowlist),
excluding evidence, results and repository history. A submitted candidate must
be available inside the container; mount its directory read-only at `/candidate`
and pass `--candidate /candidate`.

Allow **eight CPU cores and 16 GiB RAM on one node** for research and evaluation;
zero GPUs. The measured native pass-through used a four-CPU container cap.
The 10,800-second operator ceiling
allows long-surviving controllers to reach the native 10,000-step limit. An
incomplete run remains unscored rather than becoming a low model score.

The portable build and native baseline are verified on Linux/arm64.
Scores record the actual image identity used. Other architectures and
independent rebuilds need execution validation. This repository is a reviewed
proposal implementation; the generated Harbor task and full RSI-Harness
trajectory are separate downstream validation stages.

## Checks

```sh
python3 -m unittest discover -s baseline/tests -v
python3 -m unittest discover -s controller -p 'test_*.py' -v
python3 -m unittest discover -s pilot -p 'test_*.py' -v
python3 -m unittest discover -s native -p 'test_*.py' -v
ALEM_EXPORT_REPO="$PWD/../.." python3 results/test_export_alem_researcher.py
```

Canonical evaluation worlds are public. This is a fixed-workload optimization
task; it does not claim a secret test set or unseen-world generalization.
Inherited Work/Judge runtimes also remain a platform integrity limitation.
The [contract](TASK_DESIGN.md) states those boundaries explicitly.

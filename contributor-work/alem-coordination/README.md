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

The native unchanged policy separately achieved **18.93% normalized coordination reward**
over all 20 native evaluation worlds. That separate run uses the upstream
continuous transition RNG. The controller track has explicit per-world RNG and
uses the matched baseline above; never substitute the native score into a
controller improvement claim. See [all native metrics and caveats](baseline/README.md).
Low starting reward does not establish frontier researcher failure.

## Reproduce the controller evaluation

From this directory, with host Python 3.11+, Docker and one CPU node:

```sh
python3 baseline/acquire.py
python3 baseline/build.py
docker pull python@sha256:23b5dc88c7dd47fec3f960b51dc30d19df9875cfbfc60f3b62d3e5b88cbccf62
alem_image_id=$(docker image inspect --format '{{.Id}}' openrsi-alem-native20:portable)
python3 controller/launcher.py \
  --source baseline/.work/source --assets baseline/.work/assets \
  --environment-image "$alem_image_id" \
  --candidate controller/reference --suite evaluation \
  --output baseline/.work/results/controller-reference-001
```

Use a new output directory for every attempt. For a submitted controller,
replace `--candidate` with its directory containing `controller.py`. Use
`--suite dev` for the four development worlds. The environment and candidates
have no network during execution. `result.json` contains the full operator
record; only `feedback.json` is returned to a researcher during iteration.

The full lane caps the engine at four CPU cores/6 GiB and each of three workers
at one CPU core/512 MiB. Allow **eight CPU cores and 16 GiB RAM on one node** for
the host and containers together; zero GPUs. The 10,800-second operator ceiling
allows long-surviving controllers to reach the native 10,000-step limit. An
incomplete run remains unscored rather than becoming a low model score.

The portable build is verified on Linux/arm64 at the dependency-installation
level. Scores record the actual image identity used. Other architectures and
independent rebuilds need execution validation. This repository is a reviewed
proposal implementation; the generated Harbor task and full RSI-Harness
trajectory are separate downstream validation stages.

## Checks

```sh
python3 -m unittest discover -s baseline/tests -v
python3 -m unittest discover -s controller -p 'test_*.py' -v
python3 -m unittest discover -s pilot -p 'test_*.py' -v
```

Canonical evaluation worlds are public. This is a fixed-workload optimization
task; it does not claim a secret test set or unseen-world generalization.
Inherited Work/Judge runtimes also remain a platform integrity limitation.
The [contract](TASK_DESIGN.md) states those boundaries explicitly.

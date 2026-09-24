# Reproduce controller results

The exported Python controllers can be evaluated without calling a language
model or training a policy. The public JSON files also contain enough data to
recompute the reported means and paired differences without running the game.
Recreating the exact six-response research history is a separate problem; see
[the final section](#repeating-the-research-process).

Acquisition, build and replay commands were checked against the scripts; they
were not rerun to write this guide. The JSON-only recomputation example was
executed successfully against the actual main-study export. Use a fresh output
directory for every evaluation. Keep the
task revision, controller checksum, image identity and generated manifests with
any new result.

## 1. Obtain the pinned source and checkpoint

You need host Python 3.11 or newer, Git, and Docker with four CPUs and 16 GiB of
memory available for controller evaluation. No GPU is needed. Allow about 1 GiB
for downloaded source/checkpoint files and several GiB for the image; each
replay also stages its own copy of the inputs.

Run these commands from `contributor-work/alem-coordination`:

```sh
alem_task_dir="$PWD"
alem_work_dir="$alem_task_dir/baseline/.work"
python3 baseline/acquire.py --work "$alem_work_dir"
python3 baseline/acquire.py --work "$alem_work_dir" --verify-only
python3 baseline/build.py --work "$alem_work_dir"
alem_image_id=$(docker image inspect --format '{{.Id}}' openrsi-alem-native20:portable)
```

Acquisition and image building need network access. Evaluations run with the
network disabled and do not download anything. The acquisition script checks
all 291 source files and all 20 checkpoint/configuration files against the
[recorded source manifest](../baseline/source-manifest.json) and
[asset manifest](../baseline/asset-manifest.json).

The image recipe is [baseline/Dockerfile](../baseline/Dockerfile), with recorded
dependency versions in [requirements.lock](../baseline/requirements.lock).
[build.py](../baseline/build.py) verifies the inputs and prints the resulting
image identity and architecture. See the [baseline guide](../baseline/README.md)
for acquisition details and upstream terms.

The measured controller runtime used Linux arm64 and Python 3.12.14. x86_64
execution has not been validated. Its recorded image ID,
`sha256:9282bdeb7b8debc675830cf464028cba51b9a7b83afd8c1f4c098f67edd73176`,
is an immutable **local image identity**, not a public image reference that
others can pull. Use the actual ID of your build. The original complete image
and Python wheel hashes are not distributed, so an independent rebuild is not
guaranteed to have the same image ID or produce bit-identical trajectories.
Report it as a new replay with its own provenance.

## 2. Evaluate an exported controller

An export directory contains `summary.json`, `comparison.json`, `evaluations/`
and `candidates/`. Set the path to the export you want to replay:

```sh
alem_export_dir="/absolute/path/to/the/export"
python3 paper/run_evaluation.py \
  --task "$alem_task_dir" \
  --source "$alem_work_dir/source" \
  --assets "$alem_work_dir/assets" \
  --image "$alem_image_id" \
  --candidate "$alem_export_dir/candidates/selected/controller.py" \
  --suite evaluation \
  --output "$alem_work_dir/results/paper-selected-evaluation-001" \
  --evaluation-lock "$alem_work_dir/paper-evaluation.lock" \
  --run
```

The candidate argument accepts either the `controller.py` file or its directory.
To replay pass-through, use `--candidate "$alem_task_dir/controller/reference"`.
Other exported candidates are listed in the export's `summary.json`. Reuse the
same source, checkpoint, image and suite for comparisons.

Choose the suite explicitly and change the output directory each time:

| `--suite` | Worlds | Purpose |
| --- | --- | --- |
| `dev` | 20000–20003, four worlds | Development feedback and selection. |
| `evaluation` | 9999–10018, twenty worlds | Original public regression set. |
| `transfer` | 30000–30019, twenty worlds | The extension's fixed new range from the same generator. |

The `transfer` adapter changes only suite dispatch and world literals in staged
copies. It saves the patch and original/effective checksums. It does not edit
the task checkout. These worlds are not a new game, a secret test set or a
random sample of all possible maps.

The wrapper starts one ordinary container, limited to four CPUs, 16 GiB RAM and
256 processes, with zero GPUs and no network. The three agents run as separate
restricted processes inside it; no nested Docker is required. Generated code
is never imported on the host. The evaluation limit is 10,800 seconds plus
bounded shutdown time, with a 30-second limit per agent reply. The shared lock
serializes evaluations; recorded queue time is separate from execution time.

Without `--run`, the command only prepares a new staged directory and manifest.
It does not contact Docker or evaluate a policy. Do not then rerun the same
command with `--run` and the same output path: the command requires a new
directory. Choose another output path for an actual run.

The standalone wrapper accepts a newly built immutable local image ID. The
historical study exporter is stricter and checks the original frozen study and
image. Do not use that exporter to relabel a new replay as the original study.

## 3. Read the result correctly

The new output directory contains:

| File | Meaning |
| --- | --- |
| `evaluation.json` | Wrapper validation, score, validity counts and artifact identities. |
| `output/result.json` | Every world and the trusted engine's detailed result. |
| `output/feedback.json` | Aggregate feedback with no per-world records. |
| `manifest.json` and `transfer.patch` | Exact staged inputs, settings and any suite-only change. |
| `operator.private.json` and private logs | Local commands and diagnostics; do not publish them without review. |

Check both `operator_status` and the game result's `status`.
`operator_status: completed` means the wrapper completed its checks; it does not
mean the controller earned a score. A primary score requires every prescribed
world to be valid. Invalid controllers, incomplete runs and infrastructure
failures are unscored, not zero reward. Keep their records and denominators.
A naturally ended episode is not necessarily a successful episode.

The primary value is `Team/coord_reward_pct_of_max`, averaged over the complete
suite. It is a reward fraction: multiply by 100 for percent. A difference of
0.01 is one percentage point. Evaluate both selected and pass-through
controllers on the same suite for a paired comparison.

Do not substitute `baseline/replay.py` for this controller replay. That script
preserves the upstream evaluator's random-number stream across episodes. The
controller study resets a declared stream for each world, so its matched
pass-through result is a different measurement. The source, checkpoint and
Hard configuration, including `SCALE_BASE_DIFFICULTY=false`, remain fixed.

## 4. Recompute the public means without running the game

The following reads only the public export. It checks its file manifest,
recomputes complete-suite means, and prints selected-minus-reference differences.
It never imports controller code. Set `alem_export_dir` as above, then run:

```sh
python3 - "$alem_export_dir" <<'PY'
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

root = Path(sys.argv[1])
manifest = json.loads((root / 'MANIFEST.json').read_text())
for name, expected in manifest['files'].items():
    relative = Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts
    assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected
summary = json.loads((root / 'summary.json').read_text())
loaded = {}
for record in summary['final']:
    key = record['evaluation']
    if key not in loaded:
        result = json.loads((root / 'evaluations' / (key + '.json')).read_text())
        rows = result['worlds']
        assert len(rows) == result['total'] == len(result['world_ids'])
        assert [row['world_id'] for row in rows] == result['world_ids']
        complete = all(row['status'] == 'scored' for row in rows)
        if complete:
            assert all(type(row['score']) in (int, float)
                       and math.isfinite(row['score']) for row in rows)
            mean = statistics.mean(row['score'] for row in rows)
            assert math.isclose(mean, result['primary_score'], rel_tol=1e-12, abs_tol=1e-12)
            for metric, reported in result['metrics_mean'].items():
                measured = statistics.mean(row['metrics'][metric] for row in rows)
                assert math.isclose(measured, reported, rel_tol=1e-12, abs_tol=1e-12)
        else:
            assert result['primary_score'] is None
            assert not result['metrics_mean']
        loaded[key] = result
    print(record['suite'], record['label'], loaded[key]['primary_score'],
          'reused_from=', record['reused_from'])
for suite in ('evaluation', 'transfer'):
    arms = {row['label']: loaded[row['evaluation']] for row in summary['final']
            if row['suite'] == suite}
    selected, reference = arms['selected'], arms['reference']
    assert selected['world_ids'] == reference['world_ids']
    pairs = list(zip(selected['worlds'], reference['worlds']))
    complete = all(a['status'] == b['status'] == 'scored' for a, b in pairs)
    delta = statistics.mean(a['score'] - b['score'] for a, b in pairs) if complete else None
    print(suite, 'selected minus reference, percentage points:',
          None if delta is None else 100 * delta)
PY
```

Identical submitted files can share one evaluation, marked by `reused_from`.
That is result reuse, not another independent trial. The checksum checks show
that the export is internally unchanged; they do not replace the original
provenance audit. Descriptive variation across twenty worlds is not variation
across independent research attempts.

## 5. Rebuild the combined tables and figures

With both committed result directories present, run from the task directory:

```sh
python3 paper/analyze_results.py
python3 paper/check_original_replay.py
```

These use the Python standard library, check the export hashes, and recompute
`paper/study-analysis.json`, `paper/RESULTS.md` and the original-world replay
comparison. They do not call a model or run a controller. The paired differences
include every program and every declared world, with no new selection.

The plotting scripts require matplotlib and NumPy. The figures in this study
used Python 3.12.14, matplotlib 3.10.3 and NumPy 2.5.3. In an environment with
those packages, run:

```sh
python3 paper/plot_extension.py \
  --results paper/results/sol-continuation-001 --output paper/continuation
python3 paper/plot_trajectory.py
```

Both scripts write PNG and SVG files. Rebuild the tables before the trajectory
figure. Figure layout may differ with fonts or package versions; the JSON score
recomputation is independent of the plotting libraries.

## Rebuilding the original research packet

[pilot/make_packet.py](../pilot/make_packet.py) reads pinned upstream source,
the specified contract and `TASK_DESIGN.md` beside the script. Running today's
copy against today's plain-language task document would build a different
packet. To rebuild the original packet, use task files from the original pilot
commit `d4bdd34f4170d2e61f24527d7ed68b3ad0866492`:

```sh
alem_packet_tree=$(mktemp -d)
alem_repo_dir=$(git -C "$alem_task_dir" rev-parse --show-toplevel)
git -C "$alem_repo_dir" archive d4bdd34f4170d2e61f24527d7ed68b3ad0866492 \
  contributor-work/alem-coordination | tar -x -C "$alem_packet_tree"
alem_old_task="$alem_packet_tree/contributor-work/alem-coordination"
python3 "$alem_old_task/pilot/make_packet.py" \
  --source "$alem_work_dir/source" \
  --contract "$alem_old_task/controller/CONTRACT.md" \
  --output "$alem_work_dir/rebuilt-original-packet-001"
```

Use a checkout containing that Git commit and a new packet output directory.
The expected SHA-256 of `MANIFEST.json` is
`d64f2fe9425d12ae34f3e00c1ca0743e7a60569102b687195bc6c9b6a912bea3`.
The builder prints the checksum. If it differs, stop and investigate; do not
replace the expected identity with the new value. No prompts, private logs or
researcher reasoning are needed to rebuild this public source packet.

## Repeating the research process

[run_extension.py](run_extension.py) records the original six-call experiment;
it is not a turnkey recipe for generating the same six responses on another
machine. It pins two original private raw development-result files through
`PARITY_SHAS` and requires their exact bytes. The public sanitized summaries
are different files and cannot satisfy those checks. The requested
`gpt-6-sol` alias also does not identify an immutable model-server version.
Even with the same inputs, exact model responses are not guaranteed.

Controller replay and public metric recomputation are supported by the steps
above. A new research attempt needs its own declared protocol and portable
starting/parity inputs, recorded model access and budgets, and a separate
result directory. Preserve the original frozen runner and history rather than
editing their pins to make a new run appear identical. See the
[extension protocol](EXTENSION-PROTOCOL.md) and
[study review](STUDY-REVIEW.md) for selection, feedback and interpretation limits.

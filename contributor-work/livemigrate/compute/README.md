# Prepared second-model lane — not GPU validated

The local Codex pilot measures the locally available requested model only.
This independent lane is prepared for a current open-weight model, rather than
using an older small model merely to obtain low scores.

- Model: [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B/tree/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0),
  released August 2026; exact revision in `qwen38.json`. Use original BF16
  weights, text-only input, thinking enabled, `xhigh` effort.
- Server: [vLLM 0.28.0](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a),
  with the immutable Linux/amd64 image digest recorded in the profile.
- Sampling follows the model card: temperature 1.0, top-p .95, top-k 20,
  min-p 0, presence penalty 0, repetition penalty 1. Seed 0 is the initial
  prepared profile; inference is not assumed perfectly deterministic.
- Resource estimate: one physical node, one H100 80GB, 16 CPU cores, 128GiB
  host RAM. The BF16 parameter payload is approximately 55.6GB; model assets,
  runtime and cache require additional disk and memory. GPU fit and throughput
  have **not** been measured here.

The environment/SQLite grader needs no GPU. The GPU is for the frozen language
model. No weights have been downloaded, GPU rented, server started or paid API
called as part of preparing this lane.

## Execution

Download the public model at the exact revision using the official Hugging Face
snapshot interface on the supplied GPU host. Preserve its provenance and verify
the resolved weight blobs before an official run. Hugging Face cache snapshots
usually contain symlinks into a sibling `blobs` directory. Mounting only that
snapshot makes those links unusable inside Docker.

Make a separate **materialized copy** at a new destination named for the exact
revision. This local copy follows the existing cache links and requires room
for another complete model snapshot; it does not download anything. The
destination must not already exist:

```sh
python3 - <<'PY'
from pathlib import Path
import shutil
revision = '1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0'
source = Path('/absolute/cache/snapshots') / revision
destination = Path('/absolute/materialized') / revision
shutil.copytree(source, destination, symlinks=False)
PY
```

The launcher rejects every remaining symlink or non-regular entry, requires the
model/tokenizer configuration files, and checks that every shard named in the
safetensors index exists as a nonempty regular file. This checks mount
completeness; the revision directory name alone does **not** attest that the
bytes are the expected model. Before actual launch it also verifies all 32
published asset hashes against `qwen38-assets.json`: SHA256 for LFS assets and
Git blob hashes for ordinary files. The manifest was retrieved from the official
Hugging Face revision metadata on 23 September 2026; no weights were downloaded
to create it. Hashing the 55.6 GB snapshot adds disk-reading time to startup.
`--print-only` checks mount completeness but deliberately skips full content hashing.
The pinned vLLM image must already be available locally;
`--pull=never` prevents an implicit image download.

Inspect the validated launch command before starting the GPU server:

```sh
python3 compute/serve.py /absolute/materialized/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0 --print-only
python3 compute/serve.py /absolute/materialized/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
```

Only the materialized snapshot is mounted, read-only. The server uses offline
model-loading flags and exposes the inference port on loopback only.

After model loading and an actual inference/usage preflight have passed, run:

```sh
python3 pilot/run.py --mode team --inference-timeout 1800 \
  --output /absolute/new/qwen-team-run \
  --adapter-command python3 pilot/compatible_adapter.py compute/qwen38.json
```

Use `--task-root families/identity` for the independent identity task. The
central diagnostic replaces `--mode team` with
`--mode centralized`. Freeze each run's exact model profile and task revision.

The prepared profile caps each call at 32,768 total context tokens and 16,384
generated tokens, including reasoning. Six calls therefore have a conservative
196,608 input-plus-output token ceiling per family. Tokenization uses the actual
chat template; the adapter checks exact prompt token IDs, all generated token
IDs, inclusive usage, complete JSON and stop status. It never truncates context
or automatically retries a generation. A failed generation with known usage
retains it; unknown usage remains explicitly incomplete.

These resource caps are below the model's native context window. This is a
budgeted study, not a claim about unlimited model capability. The CLI diagnostic
arms also have different adaptive depth and output schemas; see the pilot
protocol before interpreting a team-versus-central score difference.

## Runtime estimate

Estimate incomplete until GPU preflight. At an illustrative aggregate decode
rate of 30–60 tokens/s, the maximum 98,304 generated tokens in one six-call family
would take roughly 27–55 minutes, plus prefill and checks. This arithmetic is
neither measured throughput nor a guaranteed runtime. Two-family evaluations
double the maximum token allowance. Actual pilot completions may be much shorter.

The task must be rechecked for headroom after measuring a strong baseline. Full
success is evidence to improve the evaluation design, not a reason to hide that
model or select a weaker one.

Protocol sources: [model card](https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/README.md),
[vLLM recipe](https://recipes.vllm.ai/Qwen/Qwen3.8-27B),
[chat schema](https://github.com/vllm-project/vllm/blob/2cf0a6915ce544dc493a0990f2ea38d81601128a/vllm/entrypoints/openai/chat_completion/protocol.py),
[tokenization schema](https://github.com/vllm-project/vllm/blob/2cf0a6915ce544dc493a0990f2ea38d81601128a/vllm/entrypoints/serve/tokenize/protocol.py).

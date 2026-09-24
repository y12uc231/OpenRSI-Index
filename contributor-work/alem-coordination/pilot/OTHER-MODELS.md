# Prepared open-model researcher lane — no GPU execution validated

`compatible_adapter.py` prepares the outer **researcher's code-generation calls** for a locally served open-weight model. The three inner Alem actors remain the same frozen HyperMARL RL policies. This file reports preparation and mocked tests, not a Qwen score or a measured GPU resource requirement. No weights were downloaded, GPU server started, API contacted or inference performed to prepare this adapter.

The adapter reuses the previously audited [LiveMigrate transport](../../livemigrate/pilot/compatible_adapter.py) at SHA256 `cd455842c6abccca0739cb052bf5f7e56e2e72ccea3d780c55242147ab946bad`. It verifies that hash before loading a private module instance. Only the task-specific schema validator changes: exactly two required string fields, `controller` and `note`, with no additional properties. The original transport file is unchanged. Its legacy JSON-schema name is only a server-side label; the actual grammar is the controller schema.

The prepared profile is [Qwen3.8-27B BF16](../../livemigrate/compute/qwen38.json), model revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, vLLM 0.28.0 and a pinned serving image. The profile file SHA256 is `65f41c78dd750993a882f58d57f84ee61d129391d5f5f47ce27dfec3fbef3119`. It retains the existing served alias `livemigrate-qwen38`; this alias is not a model task or a claim about remote weight attestation. Follow the [existing asset verification and GPU launch instructions](../../livemigrate/compute/README.md), including all pinned asset hashes. The estimated single H100 80GB lane has **not** been materialized or benchmarked. This adapter expects the Qwen/vLLM thinking-template and token-ID extensions; it is not a universal OpenAI-compatible provider implementation.

Only credential-free literal loopback addresses or `localhost` ending in `/v1` are allowed. The transport checks the serving version and alias, calls the server's native chat-template tokenizer, and reserves the entire configured output allowance before generation. The 65,536-token context and 32,768-token completion cap include reasoning. If the full public packet plus prior code and development feedback cannot fit alongside that reservation, the call stops before generation. It never truncates the packet or silently lowers the output cap. Actual fit of this task's complete packet is **unvalidated until that tokenizer preflight runs**; do not advertise this profile as already supporting the packet.

There is at most one generation request per adapter invocation, no automatic retries, and no paid-provider fallback. A completed response must have matching exact prompt token IDs, inclusive generated token IDs/usage, one choice, normal stop, complete JSON, and no tool call or refusal. Cached tokens are a subset of input tokens; reasoning is already included in generated token IDs and output tokens, and must not be added again. Failed calls retain known usage; missing or inconsistent telemetry is explicitly incomplete rather than zero. Reasoning text is never returned.

## Interface and future execution

From `contributor-work/alem-coordination`, after separately validating and starting the pinned GPU server:

```sh
python3 pilot/compatible_adapter.py ../livemigrate/compute/qwen38.json < request.json
```

`request.json` is supplied by the trusted pilot runner:

```json
{
  "prompt": "The full frozen public packet, current controller and development feedback",
  "schema": {
    "type": "object",
    "properties": {"controller": {"type": "string"}, "note": {"type": "string"}},
    "required": ["controller", "note"],
    "additionalProperties": false
  },
  "metadata_path": "new-call-directory/metadata.json"
}
```

The metadata directory must already exist, and the metadata file must not. Success writes stdout as `{response: <controller/note object>, metadata: <usage/provenance>}`. Failure exits nonzero with `response:null` and bounded error type, preserving metadata when the input identified its output path. The metadata path is never sent to the model server. Treat malformed outer JSON or an unavailable metadata destination as an operator/interface failure.

The pilot runner's prepared integration uses:

```sh
python3 pilot/run.py --model Qwen/Qwen3.8-27B \
  --packet "$ALEM_PUBLIC_PACKET" \
  --source baseline/.work/source --assets baseline/.work/assets \
  --environment-image "$ALEM_ENVIRONMENT_IMAGE" \
  --baseline-result "$ALEM_MATCHED_BASELINE_RESULT" \
  --evaluation-lock "$ALEM_EVALUATION_LOCK" --output "$ALEM_NEW_RUN_OUTPUT" \
  --adapter-command python3 pilot/compatible_adapter.py ../livemigrate/compute/qwen38.json
```

Set the five task-specific environment variables to the declared public packet directory, immutable environment-image ID, matched pass-through result, shared evaluation-lock path, and a new private output directory outside the checkout. These variables contain paths/identities, not credentials. Use the runner's `--help` to check its current interface. Declare the exact profile, three-call schedule and model identity separately before an actual external-model arm. Do not silently mix Qwen's `xhigh` template with the local Codex `ultra` setting or claim their output limits are matched. The three calls have an upper bound of 196,608 input-plus-output tokens under this profile, including at most 98,304 generated tokens. Context-fit, actual GPU memory, latency and usage behavior require a real preregistered preflight. No such inference has occurred here.

## Offline validation

```sh
python3 -m unittest discover -s pilot -p 'test_compatible_adapter.py' -v
```

Tests use a deterministic synthetic HTTP stand-in and explicitly do not yield model scores. They cover schema enforcement, context rejection before generation, loopback restriction, prompt/generated token accounting, failed-response cost retention, no retries, truncation/tool rejection, and reasoning-text exclusion.

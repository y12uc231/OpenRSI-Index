# Preparing later model comparisons

Status: provider-neutral transport is prepared. **No non-Codex model calls have been authorized or launched as part of preparation.** The only permitted wiring test during preparation uses `configs/mock.json`, a deterministic local stub with no model, network, or provider credentials.

The command entrypoint reuses the frozen nine-call workflow in `run_pilot.py` by replacing its inference function in a new process. It does not edit that file, `codex_runner.py`, or `PROTOCOL.md`, and cannot change the running Codex pilot. Use a new output directory for every later execution.

## Planned comparison matrix

| Mode | Configuration | Status | Interpretation |
| --- | --- | --- | --- |
| Original Codex CLI | Existing `run_pilot.py` | Separate local pilot | One requested model and reasoning setting; audited absence of tool events |
| Compatible Chat Completions HTTP | `configs/compatible.example.json` | Implemented, offline tests only | Explicit endpoint/key environment and supported model ID required; no live API validation |
| External OpenAI wrapper | `configs/openai.example.json` | Placeholder only | Future explicit invocation; model identifier and wrapper required |
| External Anthropic wrapper | `configs/anthropic.example.json` | Placeholder only | Future explicit invocation; model identifier and wrapper required |
| External Google wrapper | `configs/google.example.json` | Placeholder only | Future explicit invocation; model identifier and wrapper required |
| Deterministic transport stub | `configs/mock.json` | Offline wiring test | **Not a model result; no accuracy claim** |

The OpenAI/Anthropic/Google-specific example files remain honest custom-wrapper placeholders, without executable implementations. The separate `compatible.example.json` uses the included stdlib HTTP wrapper described below. Every example omits credentials, current model names, and provider-specific reasoning defaults. A user-supplied wrapper can support other transports through the same contract.

## Included compatible HTTP wrapper

`compatible_chat_command.py` implements one nonstreaming Chat Completions request with strict JSON Schema output, parses the single returned content object, and returns provider-reported model/usage. It rejects truncation, tool calls, refusals, malformed JSON, and invalid response schemas. The request shape follows the [official OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

For an explicit `openrouter.ai` endpoint it requests `require_parameters: true` and disables provider fallbacks. No response-healing plugin is enabled. Structured-output support depends on the selected model and endpoint; unsupported combinations fail rather than silently weakening the schema. See [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs) and [provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

The wrapper reads only `RELAYREPAIR_BASE_URL` and `RELAYREPAIR_API_KEY` for endpoint/authentication. There is **no default endpoint**. Set the API key through an existing secret manager or a hidden shell prompt, then export it; never put the key in a file, command argument, or displayed example. After copying `configs/compatible.example.json` to a private configuration and replacing its model placeholder, a future authorized invocation can use:

```sh
export RELAYREPAIR_BASE_URL='https://openrouter.ai/api/v1'
export RELAYREPAIR_API_KEY
python3 run_command_pilot.py --config /absolute/path/to/compatible-config.json --output /absolute/path/outside-repo/new-model-run --execute
```

These instructions have not been executed against a provider. For a local server exposing the compatible contract, the explicit base could instead be `http://127.0.0.1:8000/v1`; a key is optional only for loopback endpoints. Compatibility with a particular vLLM release/model's structured-output support still needs a later live check. Remote URLs require HTTPS, and URLs containing credentials, queries, or fragments are rejected.

Allowed scalar inference parameters are `temperature`, `top_p`, `seed`, `max_tokens`, `max_completion_tokens`, `reasoning_effort`, `frequency_penalty`, and `presence_penalty`. No parameter can replace messages, model, schema, tools, routing, credentials, streaming, or choice count. The two completion-limit parameters cannot both be supplied. Defaults do not impose a small token cap; endpoint defaults must be reported when interpreting a run. Not every endpoint supports every allowed parameter.

HTTP redirects are blocked to prevent forwarding credentials. The wrapper makes one application request without retries, has a 450-second transport timeout beneath the 480-second command timeout, and never prints headers or provider error bodies. Service-internal behavior is outside client observation. The code is covered by mocked HTTP tests, including errors, truncation, tool/refusal rejection, blocked overrides, required endpoint configuration, and redirect refusal. **No live provider calls or real credentials were used in these tests.**

## External command contract

`command` is an argv array launched without a shell. Its stdin contains one JSON object:

```json
{"messages":[{"role":"user","content":"the complete pilot prompt"}],"schema":{"type":"object"},"model":"requested-model","params":{}}
```

The actual schema is the pilot's strict object/array/string schema. The command must perform one inference, return only one JSON object on stdout, and send diagnostics to stderr:

```json
{"response":{"results":[{"case_id":"relayrepair_01","plan_id":"P1234"}]},"usage":{"input_tokens":123,"output_tokens":45},"model":"provider-returned-model-identifier"}
```

The response object must satisfy the supplied schema. Every actual case must appear; workers use `message`, while leaders use `plan_id`. `usage` may be `{}` when unavailable; missing usage is not zero usage. Report the actual provider-returned model identifier where available, or `unknown` if unavailable. Never silently substitute another model or claim the requested alias is an immutable server version.

The wrapper must keep each invocation independent, use only supplied messages, disable all tools/retrieval/history, and perform no answer correction, hidden retry, or self-consistency sampling. Provider SDK retry settings must also be disabled or explicitly documented before use. These restrictions are a **wrapper contract**: the generic transport cannot independently audit a provider's internal tools or retries. Its metadata says so. Review and hash the wrapper before making a model comparison.

Credentials belong in environment variables read by the wrapper, not command arguments, config JSON, prompts, or logs. The adapter passes the process environment without serializing it. Do not print environment variables or request headers. Configure nonsecret inference parameters in `params`; familiar credential fields are rejected. This is not a universal secret scanner, so review configs and wrapper output before sharing.

## Invocation

For an offline wiring check from this directory:

```sh
python3 run_command_pilot.py --config configs/mock.json --output /tmp/relayrepair-mock-unique --execute
```

This runs nine local stub commands, writes `mock_fixture_grading.NOT_MODEL.json`, and labels the run as a transport test. The mock emits deliberately nonpredictive strings; any fixture grading is only a wiring byproduct, never a model accuracy score.

For a future explicitly requested model run, copy and fill one example configuration, implement/review its wrapper, export credentials in the local environment, and invoke the same command with that configuration and a fresh output directory. **`--execute` launches the configured command and may incur provider charges.** Omitting it launches nothing. Preparing a config is not permission to execute it.

## Recorded artifacts and failures

The output must be outside the repository. The entrypoint records requested model, nonsecret parameters, config/code hashes, start time, and planned call count before inference. The reused workflow also hashes the fixed cases and protocol. Each call records its request, structured response, wrapper-reported model, usage, elapsed time, timeout, and zero adapter retries. `stdout.local.txt`, `stderr.local.txt`, `config.local.json`, and `runner.local.log` are local diagnostic artifacts, not a publication allowlist.

A timeout, nonzero exit, malformed envelope, or invalid structured response stops that run and preserves available output. Nothing is silently retried. Keep failed attempts; any authorized repair/rerun goes in another directory and is labeled separately. The adapter validates only the schema subset used by this pilot and rejects unsupported schema keywords rather than silently ignoring them.

## Comparability and cost caveats

- Keep the same twelve cases, ordering, nine calls, prompts, schema, and visible stale-message schedule. Do not tune on these twelve cases and then claim held-out generalization.
- Different providers have different reasoning controls, context limits, tokenizer accounting, and serving versions. Choose and record settings before running each model; do not equate parameter names or assume `ultra` has a portable meaning.
- Do not impose a small token cap merely to obtain low scores. Document any provider-required cap, truncation, or timeout and show whether it affected completion.
- This remains a one-batch-per-call smoke test. Cases are correlated and total inference costs differ. Additional model rows do not turn it into a statistically validated benchmark.
- Three worker calls can run concurrently in each round. The configured wrapper must tolerate this; provider rate limits or local capacity failures are infrastructure issues.
- The centralized condition uses one call versus the team's eight. It is a descriptive control, not a cost-matched efficiency comparison.
- Usage and dollar estimates must come from recorded provider data and explicit prices, not invented equivalences. No cost estimate or spending authorization is implied by these templates.
- Preserve and report perfect scores. A high score is evidence that the small task lacks the desired difficulty, not a reason to silently replace cases.

Use the original `PROTOCOL.md` for case definitions and scoring, with this document identifying the transport change and its weaker external audit guarantees. No formal proposal or upstream submission is created by this preparation.

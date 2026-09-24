# Prepared single-GPU validation lane

**Status: prepared, not executed. GPU access is pending.** No image or model weights were downloaded, no software installed, no credentials written, and no GPU fit/throughput result is claimed. The model and runtime revisions are verified public artifacts. This is an eight-GPU-hour validation allowance, not a prediction for the complete OpenRSI research trajectory.

One Linux physical host with one H100 80GB serves **one shared BF16 model** for two logical coding workers. Plan for 16 CPU cores, 64–128GB system RAM and at least 150GB free storage for model/image/workspace artifacts; these are planning estimates, not measured minima. Docker Engine with the NVIDIA container runtime must already work on that host. The scripts do not install them.

## Frozen artifacts and compatibility

| Asset | Pin |
| --- | --- |
| Worker model/tokenizer | `Qwen/Qwen3-Coder-30B-A3B-Instruct@b2cff646eb4bb1d68355c01b18ae02e7cf42d120`, Apache-2.0 |
| Runtime | Official vLLM `0.10.2` |
| Runtime image | `vllm/vllm-openai@sha256:607442e407b0fea97f8a132a78b787c121a996dd4de181fa08e8da06e71ec2db` (resolved from official `v0.10.2` tag) |
| Serving | BF16, tensor parallel1, context32,768 including output, maximum2 sequences, GPU memory fraction0.9 |
| Controller endpoint | `http://127.0.0.1:8000/v1`; model alias `jointverify-qwen3-coder-30b` |
| Pilot assets | [`../manifests/pilot-v1.json`](../manifests/pilot-v1.json), SHA256 recorded in [`lane-v1.json`](lane-v1.json) |

[`model-artifacts-v1.json`](model-artifacts-v1.json) lists immutable URLs, sizes and authoritative checksums for all26 runtime/documentation files, including16 weight shards. Model weights are about61.06GB (56.87GiB). Two fully occupied32K BF16 KV caches are approximately6GiB from the official48-layer/4-KV-head/128-head-dimension configuration; activations/runtime need additional memory. Hence80GB is a plausible single-GPU lane, **not a validated fit**. No quantization, CPU offload or context reduction is silently substituted if it fails.

Primary sources: [model configuration](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct/blob/b2cff646eb4bb1d68355c01b18ae02e7cf42d120/config.json), [model card](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct/blob/b2cff646eb4bb1d68355c01b18ae02e7cf42d120/README.md), [vLLM0.10.2 release](https://github.com/vllm-project/vllm/releases/tag/v0.10.2), [supported architectures](https://docs.vllm.ai/en/v0.10.2/models/supported_models.html), [versioned serve arguments](https://docs.vllm.ai/en/v0.10.2/cli/serve.html), [official Docker entrypoint usage](https://docs.vllm.ai/en/v0.10.2/deployment/docker.html). This release supports `Qwen3MoeForCausalLM`; it is a compatibility pin, not a claim to be the latest release. Native tool-call parsing is unnecessary: the controller consumes ordinary text containing one JSON action.

## Explicit preparation on the GPU host

Run these **only when GPU-host preparation is authorized**. Commands below show paths to choose; they are not existing user hosts or accounts. No Hugging Face token is required for this public checkpoint.

```bash
cd /path/to/OpenRSI-Index/contributor-work/jointverify
docker pull vllm/vllm-openai@sha256:607442e407b0fea97f8a132a78b787c121a996dd4de181fa08e8da06e71ec2db
python3 compute/download_model.py --destination /absolute/cache/jointverify-qwen3-coder
```

The download command makes network requests only to pinned public artifact URLs and their Hugging Face storage redirects. It streams files, checks LFS SHA256 or Git-blob SHA1 and sizes, and refuses to replace a mismatched existing artifact. It downloads no custom parser code and invokes no model code. Allow about61.08GB for these files, additional space for the runtime image. Partial downloads use `.part` files and restart that file on another invocation.

After preparation, the serving path performs **no download or implicit image pull**:

```bash
bash compute/serve.sh /absolute/cache/jointverify-qwen3-coder /absolute/run-state/jointverify-validation
```

The model directory is mounted read-only. The launcher verifies all artifact digests before reserving GPU time. It creates a dedicated Docker **internal** bridge without external routing, publishes only host `127.0.0.1:8000`, and enables `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `VLLM_NO_USAGE_STATS` and `DO_NOT_TRACK`. vLLM listens on `0.0.0.0` **inside that private container**, which is required for host loopback port mapping; the host listener is not public. Do not attach this container to another network. Internal networks can still reach appropriately exposed host services, so do not expose a host proxy that restores internet access. [Docker internal-network semantics](https://docs.docker.com/reference/cli/docker/network/create/#internal), [loopback port publication](https://docs.docker.com/engine/network/port-publishing/), [vLLM telemetry controls](https://docs.vllm.ai/en/v0.10.2/usage/usage_stats.html).

The first host smoke check must verify loopback access, model identity, offline behavior, actual GPU memory and two-request context capacity. Network reachability on this exact Docker/NVIDIA setup has not been tested. The worker containers remain network-disabled; only the trusted controller accesses this endpoint. No API credential is generated or stored by this setup. A localhost endpoint is a trusted-host interface, not authentication against other users on the same host.

For an already configured SSH connection, an optional tunnel from the controller machine is:

```bash
ssh -N -L 127.0.0.1:8000:127.0.0.1:8000 EXISTING_SSH_ALIAS
```

Replace `EXISTING_SSH_ALIAS` with the user's actual configured host; no hostname, user or key has been assumed. GPU serving stays local to the remote host. The controller then uses its own `127.0.0.1:8000`. This is a connection instruction, not a request to create credentials or deploy an external service.

## Token preflight and matched pilot budget

Frozen compatible-backend pilot launch defaults: **1,000,000 aggregate input + output tokens per feature pair**, at most200 requests across both workers and any model helper, at most4 public joint checks, **1,800 aggregate seconds of worker tools plus public checks**, and **3,600 seconds for the worker phase**. Mandatory final Judge grading follows even when these work budgets are exhausted. Every request has `max_completion_tokens=4096`; model context32,768 includes prompt plus that reserved output. Thus a full-cap request can contain at most28,672 prompt tokens. A typical16K prompt is a working target, not a hidden extra truncation rule. Checkpoint/history compaction must be the same declared method in all comparison arms; never drop the feature brief or selectively hide a teammate's information.

The runnable controller is wired to [`../runner/compatible.py`](../runner/compatible.py). It verifies the local server version, sends the complete system/user messages to the server's `/tokenize` native chat template, then atomically reserves the exact input count plus4,096 output tokens through `BudgetLedger` before generation. It requires returned prompt token IDs to equal preflight IDs and inclusive completion usage to equal **all** generated token IDs. Cached input and any reasoning/control tokens are counted, not subtracted. The worker sees no direct model tools. JSON-object guided output is locally checked against the strict action schema. There are no automatic retries, context truncation, remote endpoint fallback, proxy credentials, or output repairs. A refused/truncated/malformed output stops the attempt and preserves any available usage; missing usage after a started request makes the episode unscored.

With the pinned server running, the frozen CooperBench checkout and all three pilot images prepared, launch one real pilot pair from the `jointverify` directory:

```bash
JOINTVERIFY_BASE_URL=http://127.0.0.1:8000/v1 python3 -m runner.episode \
  --backend compatible --source /absolute/CooperBench \
  --task click2068_1_6 --policy periodic \
  --output /absolute/local-runs/click2068-compatible-periodic \
  --max-calls 200 --max-total-tokens 1000000 --max-checks 4 \
  --max-tool-seconds 1800 --max-episode-seconds 3600
```

Use a fresh output directory outside the contribution checkout. Other frozen task IDs are `click2800_1_3` and `dirty43_2_3`; verification-policy choices are `periodic`, `always_verify`, and `adaptive`. The additional `serial` and `centralized` modes are scheduling controls, not pure verification-only treatments: serial completes the member before handing implementation/integration/repair to the lead; centralized runs only the lead with both specifications. Keep budgets identical across comparison arms. `--backend codex` remains the default local diagnostic lane with32 calls,900 tool seconds,4 checks and3,600 worker-phase seconds. `--max-total-tokens` is rejected for Codex because that CLI lane has no enforceable per-call output cap. `--mock` exercises controller wiring without any model call and labels all artifacts `MOCK_NOT_MODEL`.

[`preflight_request.py`](preflight_request.py) uses the exact local tokenizer's native `apply_chat_template(..., tokenize=True, add_generation_prompt=True)`, including role delimiters and assistant prefix. It accepts only text chat messages and no tools/template overrides. It prepares fixed generation settings from the official model recommendation and rejects any request whose prompt plus4096 would exceed context or the shared remaining token pool. It sends no request itself. Run it inside the pinned runtime image so no host dependency installation is needed:

```bash
docker run --rm --pull never --network none --entrypoint python \
  --mount type=bind,src=/absolute/cache/jointverify-qwen3-coder,dst=/model,readonly \
  --mount type=bind,src=/absolute/path/to/jointverify/compute,dst=/compute,readonly \
  --mount type=bind,src=/absolute/request-directory,dst=/requests,readonly \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  vllm/vllm-openai@sha256:607442e407b0fea97f8a132a78b787c121a996dd4de181fa08e8da06e71ec2db \
  /compute/preflight_request.py --model-directory /model \
  --request /requests/request.json --remaining-tokens 1000000
```

Request input example:

```json
{"messages":[{"role":"user","content":"The complete worker brief and current observations go here."}],"response_format":{"type":"json_object"},"seed":1}
```

The output contains `request`, `prompt_tokens`, `output_token_limit` and `reservation_tokens`. The trusted controller must atomically reserve `prompt_tokens + 4096` through `BudgetLedger.reserve_call` **before** sending `request` to `/v1/chat/completions`, then settle using response `usage`. Concurrent reservations share the same pool. Server `prompt_tokens` must equal preflight count during validation; any mismatch or missing usage fails token-budget validation, never silently becomes zero. vLLM0.10.2 accepts [`max_completion_tokens`](https://github.com/vllm-project/vllm/blob/v0.10.2/vllm/entrypoints/openai/protocol.py); `max_tokens` is deprecated there. `--generation-config vllm` prevents model-side defaults from overriding the declared generation contract.

Count cached/retransmitted input, output, helper calls, failed calls, retries and replacement generations. The model is non-thinking; the adapter nevertheless accounts for all generated token IDs inclusively. If a failed request may have generated output but returned no usage, this controller stops budget-scored execution and preserves the failed reservation; it does not refund it or retry unmetered. The standalone preflight utility remains an offline diagnostic; the controller's server-side preflight callback enforces the aggregate budget. Exhaustion ends worker generation and submits current patches to the mandatory final Judge. It does not skip final grading or grant extra calls. Normal feature-test failure is a task failure; malformed policy/infra outcomes follow the declared separate rules.

These caps are a **pilot contract**, not measured adequate capacity or official upstream defaults. Before scientific comparison, freeze identical budgets/tool availability for the strong no-protocol team, unconditional verification and candidate policy. Keep upstream integration/inspection/repair capabilities; do not convert the local20-call diagnostic into the claimed baseline. `lane-v1.json` records the concrete tool/check and worker-phase limits. No baseline accuracy claim follows from these artifacts.

## Eight GPU-hour validation cap

[`run_capped.py`](run_capped.py) wraps the server allocation with a persistent `validation-budget.json` in the chosen state directory, counting server startup, idle time and experiment time as one-GPU wall time. Every launch must reuse that directory. It holds an exclusive lock, carries elapsed allocation forward, reserves60seconds for shutdown, and refuses to run after the cumulative28,800-second allowance is exhausted. An unfinished ledger after a crash fails closed until actual allocation has been reconciled. Do not delete/reset the ledger to extend the cap. `serve.sh` removes its specifically named container on exit. Host failure and Docker daemon failure still require checking that the allocation is stopped; this script is not a cloud billing service.

Stop before the cap if model loading OOMs, telemetry/template counts disagree, tool parsing fails, hidden assets reach workers, or fixture validation fails. Report those as operational findings, not poor model reasoning. This allowance establishes feasibility and a baseline pilot only; the duration and number of complete research loops remain unmeasured.

Offline checks performed during preparation: Python syntax, shell syntax, four token-preflight boundary tests, and a short capped-process accounting smoke test. No model execution was part of those checks.

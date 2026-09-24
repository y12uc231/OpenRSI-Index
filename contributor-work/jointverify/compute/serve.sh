#!/usr/bin/env bash
# Prepared GPU lane. No downloads, installs, authentication, or implicit pulls.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: bash compute/serve.sh /absolute/model-directory /absolute/run-state-directory" >&2
  exit 2
fi
JV_SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
JV_MODEL_DIR="$(cd -- "$1" && pwd)"
mkdir -p -- "$2"
JV_STATE_DIR="$(cd -- "$2" && pwd)"
JV_IMAGE='vllm/vllm-openai@sha256:607442e407b0fea97f8a132a78b787c121a996dd4de181fa08e8da06e71ec2db'
JV_NETWORK='jointverify-inference-internal'
JV_CONTAINER='jointverify-qwen3-coder-validation'

[[ "$(uname -s)" == Linux ]] || { echo 'This launcher requires the Linux GPU host.' >&2; exit 2; }
command -v docker >/dev/null
command -v python3 >/dev/null
docker image inspect "$JV_IMAGE" >/dev/null
if docker container inspect "$JV_CONTAINER" >/dev/null 2>&1; then
  echo "Container $JV_CONTAINER already exists; inspect its state rather than launching another allocation." >&2
  exit 2
fi
python3 "$JV_SCRIPT_DIR/download_model.py" --destination "$JV_MODEL_DIR" --verify-only
if docker network inspect "$JV_NETWORK" >/dev/null 2>&1; then
  [[ "$(docker network inspect --format '{{.Internal}}' "$JV_NETWORK")" == true ]] || {
    echo 'Existing inference network is not internal; refusing external connectivity.' >&2; exit 2;
  }
else
  docker network create --driver bridge --internal "$JV_NETWORK" >/dev/null
fi

cleanup() { docker rm -f "$JV_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT
# Device zero is one physical GPU. Confirm it is the intended 80GB GPU before launch.
# Host publication is loopback-only; 0.0.0.0 below is inside the private container.
python3 "$JV_SCRIPT_DIR/run_capped.py" --ledger "$JV_STATE_DIR/validation-budget.json" -- \
  docker run --rm --pull never --name "$JV_CONTAINER" \
    --gpus device=0 --network "$JV_NETWORK" -p 127.0.0.1:8000:8000 \
    --shm-size 8g --cap-drop ALL --security-opt no-new-privileges \
    --mount "type=bind,src=$JV_MODEL_DIR,dst=/model,readonly" \
    -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
    -e VLLM_NO_USAGE_STATS=1 -e DO_NOT_TRACK=1 \
    "$JV_IMAGE" \
    --model /model --tokenizer /model \
    --served-model-name jointverify-qwen3-coder-30b \
    --dtype bfloat16 --tensor-parallel-size 1 \
    --max-model-len 32768 --max-num-seqs 2 \
    --gpu-memory-utilization 0.9 --generation-config vllm \
    --host 0.0.0.0 --port 8000 --no-enable-log-requests

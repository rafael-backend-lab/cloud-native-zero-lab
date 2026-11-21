#!/usr/bin/env bash
set -euo pipefail
: "${LAB_ACCESS_PASSWORD:?Defina a senha de acesso pessoal}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=0
export GOMEMLIMIT="${GOMEMLIMIT:-280MiB}"
export GOGC="${GOGC:-50}"
ollama serve &
model_pid=$!
api_pid=""
cleanup() {
  kill "$model_pid" ${api_pid:+"$api_pid"} 2>/dev/null || true
}
trap cleanup EXIT
python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" &
api_pid=$!
wait -n "$model_pid" "$api_pid"

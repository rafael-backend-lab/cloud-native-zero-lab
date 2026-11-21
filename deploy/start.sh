#!/usr/bin/env bash
set -eu
: "${LAB_ACCESS_PASSWORD:?Defina a senha de acesso pessoal}"
ollama serve &
model_pid=$!
trap 'kill "$model_pid" "${api_pid:-}" 2>/dev/null || true' EXIT
python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" &
api_pid=$!
wait -n

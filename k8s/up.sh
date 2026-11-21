#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cluster=zero-lab
ctx=k3d-zero-lab
ns=zero-lab
k() { kubectl --context "$ctx" -n "$ns" "$@"; }
if ! k3d cluster list --no-headers | awk '{print $1}' | grep -Fxq "$cluster"; then
  k3d cluster create "$cluster" --api-port 127.0.0.1:6550 -p '127.0.0.1:8443:443@loadbalancer' --wait
fi
kubectl --context "$ctx" create namespace "$ns" --dry-run=client -o yaml | kubectl --context "$ctx" apply -f -
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
if [[ -z "$(k get secret db-passwords --ignore-not-found -o name)" ]]; then
  for key in admin api; do openssl rand -hex 32 | tr -d '\n' > "$tmp/$key"; done
  k create secret generic db-passwords --from-file=admin="$tmp/admin" --from-file=api="$tmp/api"
fi
if [[ -z "$(k get secret entrada-tls --ignore-not-found -o name)" ]]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj /CN=localhost -addext subjectAltName=DNS:localhost -keyout "$tmp/key" -out "$tmp/cert" 2>/dev/null
  k create secret tls entrada-tls --key="$tmp/key" --cert="$tmp/cert"
fi
k create configmap db-init --from-file=k8s/postgres-init.sh --dry-run=client -o yaml | k apply -f -
docker build -t zero-lab-api:local .
k3d image import zero-lab-api:local -c "$cluster"
k apply -f k8s/stack.yaml
k rollout restart deployment/api
for svc in api postgres ollama; do k rollout status "deployment/$svc" --timeout=6m; done
k exec deployment/ollama -- ollama pull qwen2.5:0.5b
echo 'FastAPI disponível em https://localhost:8443/docs'

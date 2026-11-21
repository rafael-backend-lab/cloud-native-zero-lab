#!/usr/bin/env bash
set -euo pipefail
k() { kubectl --context k3d-zero-lab -n zero-lab "$@"; }
# Carga de CPU limitada a um pod do cluster descartável do laboratório.
pod=$(k get pods -l app=api -o jsonpath='{.items[0].metadata.name}')
k exec "$pod" -- python -c 'import time
end=time.monotonic()+210
while time.monotonic()<end: pass' &
load_pid=$!
trap 'kill "$load_pid" 2>/dev/null || true' EXIT
for i in {1..38}; do
  ready=$(k get deployment api -o jsonpath='{.status.readyReplicas}')
  if [[ ${ready:-0} -gt 2 ]]; then echo "HPA: $ready réplicas prontas durante a carga"; exit 0; fi
  sleep 5
done
k describe hpa api
exit 1

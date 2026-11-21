#!/usr/bin/env bash
set -euo pipefail
k() { kubectl --context k3d-zero-lab -n zero-lab "$@"; }
cert=$(mktemp)
trap 'rm -f "$cert"' EXIT
k get secret entrada-tls -o 'jsonpath={.data.tls\.crt}' | openssl base64 -d -A > "$cert"
api() { curl --silent --show-error --fail --cacert "$cert" "https://localhost:8443/$1" "${@:2}"; }
for i in {1..60}; do if api dbstatus | jq -e '.user=="lab_api"' >/dev/null; then break; fi; sleep 2; done
api dbstatus | jq -e '.database=="lab" and .user=="lab_api"'
id=$(api messages -H 'Content-Type: application/json' -d '{"mensagem":"Teste HTTPS"}' | jq -er .id)
api messages | jq -e --argjson id "$id" 'any(.messages[]; .id==$id and .mensagem=="Teste HTTPS")'
api ia -H 'Content-Type: application/json' -d '{"pergunta":"Quanto é dois mais dois?"}' | jq -e '.resposta | strings | length > 0'
k get deployment api -o json | jq -e '.status.readyReplicas >= 2'
# Mesmo namespace, sem o rótulo da API. DNS deve resolver antes da verificação da porta.
k run "rede-$RANDOM" --image=zero-lab-api:local --image-pull-policy=Never --restart=Never --rm -i --command -- python -c '
import socket
for host, port in [("postgres", 5432), ("ollama", 11434)]:
    address = socket.gethostbyname(host)
    try:
        conn = socket.create_connection((address, port), timeout=4)
    except (TimeoutError, ConnectionRefusedError, ConnectionResetError):
        print(host, "bloqueado", flush=True)
    else:
        conn.close()
        raise SystemExit(f"Acesso inesperado a {host}")
'

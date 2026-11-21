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
k run "rede-$RANDOM" --image=busybox:1.36 --restart=Never --rm -i --command -- sh -ec 'for item in postgres:5432 ollama:11434; do h=${item%:*}; p=${item#*:}; nslookup "$h" >/dev/null; if nc -w 3 "$h" "$p" </dev/null; then exit 1; fi; done'

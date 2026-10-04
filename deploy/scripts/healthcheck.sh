#!/usr/bin/env bash
set -euo pipefail

root=${CLARITY_DEPLOY_ROOT:-/opt/hutch-clarity}
compose=(docker compose --env-file "$root/.env.production" -f "$root/deploy/compose/vps.yml")

# Every internal check in one Python process inside clarity-api: each
# `docker compose exec` costs about a second, and there were fourteen.
"${compose[@]}" exec -T clarity-api python - <<'PY'
import socket
import urllib.request

ports = {
    "postgres": 5432, "kafka": 19092, "keycloak": 8080, "opa": 8181,
    "clarity-api": 8000, "clarity-mcp": 8099, "clarity-channel-gateway": 8102,
    "hutch-sim": 8103, "customer-web": 3000, "clarity-console": 3000,
    "receipt-verify": 3000,
}
for host, port in ports.items():
    socket.create_connection((host, port), 5).close()
for url in (
    "http://clarity-api:8000/health",
    "http://clarity-channel-gateway:8102/health",
    "http://hutch-sim:8103/health",
):
    urllib.request.urlopen(url, timeout=5)
PY

if grep -q '^WHATSAPP_ENABLED=true$' "$root/.env.production"; then
  "${compose[@]}" --profile whatsapp exec -T clarity-whatsapp node -e \
    "fetch('http://127.0.0.1:8104/health').then(async r => { const body = await r.json(); if (!r.ok || !body.paired || !body.connected) process.exit(1) })"
fi

curl_flags=(--fail --silent --show-error --max-time 15)
if [[ ${CLARITY_BOOTSTRAP_TLS:-0} == 1 ]]; then
  curl_flags+=(--insecure)
fi
curl "${curl_flags[@]}" https://116.203.101.73/ >/dev/null
curl "${curl_flags[@]}" https://116.203.101.73/health | grep -q '"status":"ok"'
curl "${curl_flags[@]}" https://116.203.101.73:8443/ >/dev/null
curl "${curl_flags[@]}" https://116.203.101.73:9443/ >/dev/null

for port in 5432 9092 8081 8181 8200 8000 8099 8102 8103 8104 3000 3001 3002; do
  if ss -lntH | awk '{print $4}' | grep -Eq "(^|:)$port$"; then
    echo "internal port $port is publicly bound" >&2
    exit 1
  fi
done
echo "all Clarity health checks passed"

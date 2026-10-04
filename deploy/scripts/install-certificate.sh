#!/usr/bin/env bash
set -euo pipefail

root=${CLARITY_DEPLOY_ROOT:-/opt/hutch-clarity}
source_dir=/etc/letsencrypt/live/116.203.101.73
install -m 0644 "$source_dir/fullchain.pem" "$root/tls/fullchain.pem"
install -m 0600 "$source_dir/privkey.pem" "$root/tls/privkey.pem"
docker compose --env-file "$root/.env.production" -f "$root/deploy/compose/vps.yml" \
  exec -T reverse-proxy nginx -s reload

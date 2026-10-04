#!/usr/bin/env bash
set -euo pipefail

root=${CLARITY_DEPLOY_ROOT:-/opt/hutch-clarity}
compose=(docker compose --env-file "$root/.env.production" -f "$root/deploy/compose/vps.yml")
install -d -m 0700 "$root/backups"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$root/backups/clarity-$stamp.sql.gz"
"${compose[@]}" exec -T postgres sh -c 'exec pg_dumpall -U "$POSTGRES_USER"' | gzip -9 > "$target"
test -s "$target"
gzip -t "$target"
chmod 0600 "$target"
find "$root/backups" -maxdepth 1 -type f -name 'clarity-*.sql.gz' -printf '%T@ %p\n' \
  | sort -nr | awk 'NR > 7 {$1=""; sub(/^ /,""); print}' | xargs -r rm --
echo "$target"

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "usage: $0 <git-sha>" >&2
  exit 64
fi
root=${CLARITY_DEPLOY_ROOT:-/opt/hutch-clarity}
candidate=$1
environment=$root/.env.production
compose=(docker compose --env-file "$environment" -f "$root/deploy/compose/vps.yml")

current=""
[[ -f $root/current-release ]] && current=$(<"$root/current-release")
if [[ -n $current && $current != "$candidate" ]]; then
  printf '%s\n' "$current" > "$root/previous-release"
fi
if "${compose[@]}" ps --status running postgres --quiet | grep -q .; then
  "$root/deploy/scripts/backup.sh"
fi

sed -i -E "s/^IMAGE_TAG=.*/IMAGE_TAG=$candidate/" "$environment"
export IMAGE_TAG=$candidate
"${compose[@]}" config --quiet
"${compose[@]}" pull
"${compose[@]}" up -d --wait --remove-orphans
# Recreate, not reload: the configs are single-file bind mounts, and the
# release tarball replaces those files, so a running proxy keeps reading the
# old ones. Recreating also picks up the new container addresses at once.
"${compose[@]}" up -d --force-recreate --no-deps --wait reverse-proxy
if ! "$root/deploy/scripts/healthcheck.sh"; then
  "$root/deploy/scripts/rollback.sh"
  exit 1
fi
printf '%s\n' "$candidate" > "$root/current-release"
echo "deployed $candidate"

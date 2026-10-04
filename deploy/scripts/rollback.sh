#!/usr/bin/env bash
set -euo pipefail

root=${CLARITY_DEPLOY_ROOT:-/opt/hutch-clarity}
environment=$root/.env.production
compose=(docker compose --env-file "$environment" -f "$root/deploy/compose/vps.yml")
if [[ -s $root/previous-release ]]; then
  previous=$(<"$root/previous-release")
  [[ $previous =~ ^[0-9a-f]{7,40}$ ]]
  sed -i -E "s/^IMAGE_TAG=.*/IMAGE_TAG=$previous/" "$environment"
  export IMAGE_TAG=$previous
  # The previous release's images are already on this host. Pulling again
  # would need a registry login that expired with the deploy job, and a
  # release built on the host has no registry copy at all.
  "${compose[@]}" up -d --wait --pull missing
  "$root/deploy/scripts/healthcheck.sh"
  printf '%s\n' "$previous" > "$root/current-release"
  echo "rolled back Clarity to $previous"
  exit 0
fi

"${compose[@]}" stop || true
if [[ -s $root/previous-project-containers.txt ]]; then
  xargs -r docker start < "$root/previous-project-containers.txt"
  echo "first Clarity deployment stopped; previous project restarted"
else
  echo "no previous Clarity release or previous-project restart file" >&2
  exit 1
fi

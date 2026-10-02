#!/usr/bin/env bash
# Echo annotated git tag commands for the architecture baseline.
# Does NOT run git tag unless you pass --execute (still refuses if dirty).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"  # repository root (script lives in backend/scripts)
VERSION_FILE="${ROOT}/VERSION"
VERSION="$(tr -d '[:space:]' < "${VERSION_FILE}")"

BASELINE_TAG="baseline-v1"
RELEASE_TAG="v1.0"

cat <<EOF
# Hutch Clarity tag helper (safe by default: prints only)

VERSION file : ${VERSION}
Suggested annotated tags:
  ${BASELINE_TAG} - architecture / profile / driver parity baseline
  ${RELEASE_TAG} - milestone release (only when submission-ready)

Dry-run commands:

  git tag -a ${BASELINE_TAG} -m "Architecture baseline ${VERSION}"
  git tag -a ${RELEASE_TAG} -m "Hutch Clarity ${RELEASE_TAG} (${VERSION})"

Push (only after local review):

  git push origin ${BASELINE_TAG}
  git push origin ${RELEASE_TAG}

EOF

if [[ "${1:-}" != "--execute" ]]; then
  echo "No tags created. Re-run with --execute to create local annotated tags."
  exit 0
fi

if [[ -n "$(git -C "${ROOT}" status --porcelain)" ]]; then
  echo "Working tree is dirty; refusing to tag. Commit or stash first." >&2
  exit 1
fi

echo "Creating local annotated tags…"
git -C "${ROOT}" tag -a "${BASELINE_TAG}" -m "Architecture baseline ${VERSION}"
git -C "${ROOT}" tag -a "${RELEASE_TAG}" -m "Hutch Clarity ${RELEASE_TAG} (${VERSION})"
echo "Done. Push explicitly when ready (commands printed above)."

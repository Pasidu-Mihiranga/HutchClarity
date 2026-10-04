# 2026-10-04 - UI02 - Autopsy and Foresight workspaces

| Field | Value |
|---|---|
| Author(s) | agent: Codex wrote the code and this entry |
| Work package | UI02 |
| PR / commit | not committed |
| Units touched | console frontend |

## What changed

- Added permission-aware Complaint Autopsy and Foresight navigation.
- Added dedicated API-driven workspaces with synthetic provenance, hypotheses,
  masked examples, trends, mitigations and baseline-vs-swarm comparison.
- Removed two prohibited em dashes introduced on the latest upstream `main`
  while integrating the branch.

## Why

UI02 requires operational workspaces without duplicating backend logic in
React.

## Decisions made

- Both screens use existing SDK methods and `desk:queue:read` authorization.
- No production rule activation or customer-changing action is exposed.

## Docs updated

- [x] Frontend README route inventory
- [x] WT-13 staff console walkthrough and submission demo script

## Tests

- Console strict TypeScript check passed.
- `npm install` passed, reporting the repository's existing dependency audit
  findings: 6 high and 1 critical.
- Native-filesystem production build compiled, type-checked, prerendered and
  optimized all three apps; console routes `/autopsy` and `/foresight` are in
  the build output. The mounted workspace itself makes Next's worker exit with
  `SIGBUS`, so the same source was verified from `/tmp`.
- UI02 browser journeys: 3 passed. Complete Playwright suite: 19 passed.
- SDK schema check and console strict TypeScript check passed.
- Final `make check`: 1,997 passed, 544 skipped in 47.97s; lint, format, strict
  typing and all three import contracts clean.

## Open issues / next step

- Next.js 14 still emits the upstream lockfile-patching warning recorded by
  FE01/FE02. It is non-fatal in dev and the isolated production build.

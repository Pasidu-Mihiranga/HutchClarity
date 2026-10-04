# 2026-10-04 - CI - main green again, demo VPS deploy unblocked

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code |
| Work package | CI / CD01 (deploy demo VPS) |
| PR / commit | branch `claude/great-dijkstra-lmd2fd` |
| Units touched | customer-web (chat page), frontend e2e |

## What changed
- `customer-web/app/clarity/page.tsx`: removed the client-side eligibility gate that called `accountIntents(account)`. The function was deleted in f349edc (A2), but a later merge brought the call back, so `next build` failed with `Cannot find name 'accountIntents'`.
- `e2e/thinking-orb.spec.ts`: the spec holds both turn routes (`/v1/conversation/turn` and `/turn/stream`). The chat now asks over the stream route (A5), so the old glob held nothing and the stage events replaced the "Thinking" label before the assertion.

## Why
`deploy demo VPS` runs on `workflow_run` of `ci` and only when CI succeeds on main. Every main push since #87 had red CI, so every deploy run was **skipped**. Three CI jobs were red:
- `frontend (typecheck and build)` and `deployment artefacts`: the `accountIntents` type error.
- `browser journeys`: the same missing function at runtime in `next dev`, plus the thinking-orb route glob. Each failure restarted the Playwright worker, which drops the cached customer token, so later voice specs hit the OTP challenge budget (429). Those 429s were a cascade, not a separate defect.

## Decisions made
- Restored the A2 behaviour (no client gate; rules decide, I1) instead of reintroducing `accountIntents`.

## Docs updated
- [x] This devlog
- No `MODULE.md` (frontend app, no backend module touched), no contract change.

## Tests
- `npm run typecheck && npm run build` in `frontend/`: all three apps build.
- `npx playwright test` (CI=1, lite API): `42 passed`.

## Open issues / next step
- Once this lands on main and CI is green, the deploy workflow runs on its own; no workflow change is needed.

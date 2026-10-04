# [CD01] CI-gated deployment to demo VPS

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `deploy` |
| Priority | P1 |
| Depends on | DEP01, B10 |
| Plan | 12 §23; 21 §7 R7 |
| Labels | `wave:w5`, `area:deploy`, `priority:p1`, `type:feature` |

## Scope

- Preserve the existing blocking CI workflow and deploy only CI-approved `main` commits.
- Publish the backend and three frontend images to GHCR with immutable SHA tags.
- Use the protected `demo-vps` environment, a dedicated SSH key and pinned host key.
- Keep application secrets on the VPS, back up before upgrade and roll back by health.
- Support manual redeploy and rollback without rebuilding.

## Acceptance tests

- Pull requests and failed CI runs never deploy.
- One successful `main` run deploys and passes live health checks.
- A deliberate failed candidate returns to the recorded previous SHA.
- The VPS secret file is never uploaded by CD.

GitHub: #58.

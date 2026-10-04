# 2026-10-04 - CD01 - Faster deploys

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | CD01 #58 |
| PR / commit | branch `ci/faster-deploy` |
| Units touched | `.github/workflows/deploy-vps.yml`, `deploy/compose/vps.yml`, `deploy/scripts` |

## What changed
- The deploy workflow has three jobs: `release` (resolve the SHA, no secrets), `build` (a matrix of four runners, one image each, own cache scope), and `deploy` (the only job in the `demo-vps` environment). Rollback skips `build`.
- `deploy.sh` pulls with `--policy missing`: the release's four images are new tags, and the pinned infrastructure images are already on the host.
- Seven health checks probe every 2 seconds while starting (`start_period: 120s`, `start_interval: 2s`), then every 10 seconds as before.
- `healthcheck.sh` runs every internal check in one Python process instead of fourteen `docker compose exec` calls.

## Why
The last deploys spent 114 to 225 seconds building four images in series and about 91 seconds on the server, much of it waiting up to 10 seconds per tier of the start chain for the next health probe.

## Decisions made
- No change to the CI gate: deploys still wait for `ci` on `main`.
- Failures during `start_period` do not count against `retries`, so a slow first start is not reported unhealthy early.

## Docs updated
- [ ] None: procedures unchanged

## Tests
- `actionlint`: no errors (two SC2029 notes about intended client-side expansion that predate this change).
- On the VPS: `pull --policy missing` took 0.2 seconds and skipped every present image; the new `healthcheck.sh` passed (4.1 seconds including ssh, against 4.7 seconds for the old one on the host).
- `docker compose config` on the changed `vps.yml`: valid.

## Open issues / next step
- Measure the next real CD run end to end.

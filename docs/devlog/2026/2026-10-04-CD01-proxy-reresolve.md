# 2026-10-04 - CD01 - Reverse proxy re-resolves recreated containers

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | CD01 #58 |
| PR / commit | branch `fix/deploy-proxy-reresolve` |
| Units touched | `deploy/nginx`, `deploy/scripts` |

## What changed
- `vps.conf`: upstreams use Docker's DNS (`resolver 127.0.0.11`) with `server ... resolve` and a shared-memory zone, so Nginx follows a container to its new address.
- `deploy.sh` and `rollback.sh` reload the proxy after `up`, so new addresses take effect at once.

## Why
The first CD run (37181509630, SHA `83cd2c3`) started every container healthy, but the health check got 502 from the proxy: Nginx still sent traffic to the addresses it resolved at start, and `up` had recreated the frontends with new ones. `deploy.sh` rolled back to `01d1762` as designed; that recreated the containers again, so the rollback health check also got 502 and the job failed. The verifier on :9443 answered 502 until the proxy was reloaded by hand (06:07 UTC).

## Decisions made
- Re-resolution in Nginx (open source since 1.27.3, image is 1.28) fixes the cause, including containers the restart policy recreates; the reload is the immediate path.

## Docs updated
- [ ] deploy README: no procedure changed

## Tests
- `nginx -t` with `nginx:1.28-alpine` on a user-defined Docker network: syntax ok, test successful.
- `bash -n` on both scripts.
- Live proof is the next CD run on `main`.

## Open issues / next step
- Exercise the CD rollback (`workflow_dispatch`, `operation=rollback`) once a release is current.

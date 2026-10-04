# 2026-10-04 - DEP01 - Security headers reach proxied responses

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | DEP01 #57 (brief §19 reverse proxy security) |
| PR / commit | branch `fix/deploy-security-headers` |
| Units touched | `deploy/nginx` |

## What changed
- `clarity-proxy.conf` no longer calls `add_header`. `Cache-Control: no-store` moved to `clarity-security.conf`, next to the other headers.
- `Permissions-Policy` comes from a `map` on the port: `microphone=(self)` on the customer origin (443) for the chat's opt-in voice input; `microphone=()` on the Desk (8443) and the verifier (9443).

## Why
In Nginx, an `add_header` inside a `location` replaces every header inherited from the server. `clarity-proxy.conf` (included in every proxied location) added `Cache-Control`, so the live site sent no HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy or Permissions-Policy. Checked with `curl -D -` against https://116.203.101.73/ before the fix.

## Decisions made
- The microphone is allowed only on the origin that has a feature needing it.
- Static assets stay `no-store`, as before; caching them is a separate change.

## Docs updated
- [ ] None: no procedure changed

## Tests
- `nginx:1.28-alpine` with the three configs, `curl -D -` on each port: all six security headers present; Permissions-Policy is `microphone=(self)` on 443 and `microphone=()` on 8443 and 9443.
- The CSP is now enforced for the first time; the live check after deploy is a browser run against the VPS.

## Follow-up after the deploy
- CD deployed `d627bfd`, but the proxy still sent the old headers. The configs are single-file bind mounts, and the release tarball replaces the files with new inodes, so the running container kept the old files, and `nginx -s reload` re-read those same old files. `deploy.sh` and `rollback.sh` now recreate the proxy container (`up -d --force-recreate --no-deps --wait reverse-proxy`). The live proxy was recreated by hand once to apply this release.
- Live check: all three origins send HSTS, CSP, X-Frame-Options and Permissions-Policy (microphone only on 443). A Playwright run against the VPS (customer sign-in and a chat turn as `+94782223333`, the Desk and the verifier) reported no CSP violations or page errors, and the chat reached "I found the reason".

## Open issues / next step
- None.

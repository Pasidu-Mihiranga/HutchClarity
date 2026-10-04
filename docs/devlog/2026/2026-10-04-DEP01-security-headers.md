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

## Open issues / next step
- Browser check of all three apps on the VPS after the CD deploy.

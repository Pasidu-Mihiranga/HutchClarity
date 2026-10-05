# 2026-10-05 - console - AccessDenied redirects to an allowed section

| Field | Value |
|---|---|
| Author(s) | agent: Composer |
| Work package | E2 (console shell) |
| PR / commit | feat/console-sidebar-mcp (local) |
| Units touched | frontend/apps/console |

## What changed
- `AccessDenied` sends a signed-in identity to the first section their
  permissions allow (shared `CONSOLE_SECTIONS` map), instead of leaving them
  on a dead refusal card.
- Added **Offers** to the sidebar (gated on `offer:manage`) for security admin.
- Four-eyes footer on the stuck refusal only when the need is desk/approve.

## Why
`security_admin` opening `/desk` saw "Needs: desk:queue:read" plus four-eyes
copy that does not apply. Role-only nav already hides Desk; a direct URL or
stale tab should follow the same map.

## Decisions made
- Redirect target order matches the sidebar (Offers before Audit/Admin).
- Brief status "Opening {section}…" while `router.replace` runs.

## Docs updated
- [x] Devlog (this file)
- [ ] Walkthrough (no step change; behaviour softens step 5 for auditor)

## Tests
`npm run test -- test/ConsoleNav.test.tsx` in `frontend/apps/console`.

## Open issues / next step
None.

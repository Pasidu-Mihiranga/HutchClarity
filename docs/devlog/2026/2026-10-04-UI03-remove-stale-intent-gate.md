# 2026-10-04 - UI03 - Remove stale client intent gate

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | main integration repair |
| PR / commit | pending |
| Units touched | customer-web chat |

## What changed

- Removed the remaining call to the deleted `accountIntents` client heuristic.
- Let the backend rule engine evaluate account questions as the surrounding
  flow already requires.
- Made the thinking-orb assertion accept the valid first streamed provider
  stage when it arrives before Playwright observes the local initial label.
- Added a bounded schema diff to a failed OpenAPI freshness check so CI shows
  the environment-specific mismatch instead of only saying it exists.
- Regenerated OpenAPI and SDK outputs after the staff SSO PR merged into main
  without those generated artifacts.

## Why

Recent main-branch changes removed the heuristic because it could suppress a
valid backend decision, but one call site remained and broke the production
customer-web build.

## Decisions made

- The client does not decide whether account evidence is sufficient.

## Docs updated

- [x] Integration repair recorded here
- [ ] MODULE.md: no domain module behavior changed
- [ ] ARCHITECTURE.md / modules.md: no architecture change
- [ ] CHANGELOG.md / contracts: no public contract change
- [ ] Plan via CHANGES.md: no plan change

## Tests

- Customer-web production build: passed. Next.js emitted its existing optional
  SWC lockfile patch warning after producing the build.
- Customer-web copy tests: 4 passed.
- Repository gate after the final main rebase: 2,501 passed, 638 skipped.
- OpenAPI and generated SDK contract checks: passed.
- CI browser run before the timing assertion repair: 41 passed, 1 failed.
- Focused thinking-orb browser journey after repair: 1 passed.

## Open issues / next step

Deploy with the live-channel fixes and recheck the signed-in chat flow.

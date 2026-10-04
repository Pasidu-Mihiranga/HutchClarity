# 2026-10-04 - console - IgniteX desk

| Field | Value |
|---|---|
| Author(s) | agent: Grok |
| Work package | FE01 console presentation |
| PR / commit | not committed |
| Units touched | frontend/apps/console |

## What changed
- Restyled Clarity Desk to the IgniteX palette: white, ink, Hutch orange `#ff6601`, Inter and Space Grotesk.
- Moved staff identity into the header and removed the amber demo banner and the fixed bottom bar.
- Replaced demo wording with synthetic-record wording. Approval, role names, and the synthetic seed actions stay.

## Why
The staff console read as a hackathon demo. The desk should look like the IgniteX site while the data stays synthetic (I16).

## Decisions made
- Theme stays inside the console app. Shared `@clarity/ui` sky buttons are recolored only by console CSS, so customer-web is unchanged.
- Vertex AI was checked on the VPS and is not part of this change. The deployed release has no Vertex settings.

## Docs updated
- [ ] MODULE.md of: none (frontend console)
- [ ] ARCHITECTURE.md / modules.md
- [x] Walkthrough: WT-13 staff console
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
Local console on port 3011 against the API on port 8000. A supervisor loaded a synthetic case and the page issued a Trust Receipt. An auditor was refused the desk. Desktop and mobile layouts were checked. Not deployed.

## Fonts (agent: Claude Code, Claude Opus 5.5)
- `next/font/google` downloads Inter and Space Grotesk at build time; the CI runner's build failed there (`next/font`: Cannot read properties of null). The fonts now come from `@fontsource-variable/inter` and `@fontsource-variable/space-grotesk` (OFL-1.1, OSI-approved; I17), bundled with the app: no build-time download, and nothing outside `font-src 'self'` at runtime.

## Open issues / next step
VPS still serves `339ab00`. Latest `main` (`c0fbfaf`) failed `mypy` and was not deployed. Vertex remains on `feat/vai01-vertex-ai`, not on the VPS.

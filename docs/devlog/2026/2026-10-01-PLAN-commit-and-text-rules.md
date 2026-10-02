# 2026-10-01 - PLAN - Commit rules and no-em-dash rule

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Anthropic), working with the team lead |
| Work package | Pre-A (planning) |
| PR / commit | not yet committed |
| Units touched | AGENTS.md, CONTRIBUTING.md, PR template, all docs |

> **Context:** recorded in the v1.2 plan line ("Plan v1"), before the merge. Its chapters 17-19 are chapters 18-20 of the merged plan, and its ADR-0001…0014 are ADR-0011…0024.

## What changed
- AGENTS.md: added I18 (no em dash anywhere) and I19 (one author per commit, no attribution)
- AGENTS.md: added section 10.1 commit rules with an example
- Replaced every em dash in the repository
- Rules are checked in review (no automated scripts in the handover)

## Docs updated
- [x] AGENTS.md, CONTRIBUTING.md, PR template, CHANGELOG.md

## Tests
- 0 em dashes left in the repository
- Mermaid: 44 diagrams render with Mermaid 11

## Open issues / next step
- Each developer turns off co-author attribution in their AI coding tools

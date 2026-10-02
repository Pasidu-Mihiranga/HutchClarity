# 2026-10-01 - PLAN - Runtime profiles (ADR-0014, plan v1.2)

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Anthropic), working with the team lead |
| Work package | Pre-A (planning) |
| PR / commit | not yet committed |
| Units touched | enterprise-plan 04, 12, 17, 18, CHANGES, README; ADR-0014; AGENTS.md; ARCHITECTURE.md |

## What changed
- Added runtime profiles `lite`, `full`, `prod` with a driver matrix (17 §2.3)
- Added local database workflow (17 §2.4) and configuration and secrets rules (17 §2.5)
- A1 now delivers the `lite` profile (PostgreSQL only); Compose `full` profile moved to new work package I0
- Added Gantt section I (I0 to I3: real drivers and observability in a CI lane); M4 now depends on them
- AGENTS.md: I20 (no profile checks in business code), I14 extended, new commands
- ADR-0014 accepted; plan version 1.2

## Docs updated
- [x] ARCHITECTURE.md (runtime profiles), ADR index, WALKTHROUGHS (WT-01), README, CHANGELOG, plan CHANGES.md

## Tests
- Text style check, link check and Mermaid render check (results in the PR)

## Open issues / next step
- Next work package: A1

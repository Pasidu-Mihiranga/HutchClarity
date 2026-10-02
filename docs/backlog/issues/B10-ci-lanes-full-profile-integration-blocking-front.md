# [B10] CI lanes: full-profile integration, blocking frontend build, real secret scanning and SBOM

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `ci` |
| Priority | P1 |
| Depends on | [B05](B05-postgresql-repositories-schema-and-role-per-modu.md) |
| Plan | 12 §23 |
| Labels | `wave:w0`, `area:ci`, `priority:p1`, `type:baseline` |

## Context
CI runs only the `lite` backend job; frontend is non-blocking; gitleaks and SBOM are placeholders.

## Scope
- `full` lane with PostgreSQL (and Kafka once B03) as GitHub service containers
- Frontend job blocking once green
- gitleaks action; Syft SBOM; licence check

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a PR that breaks the PostgreSQL parity suite | CI runs | the `full` lane fails | `CI` |
| 2 | a commit containing a fake AWS key | CI runs | gitleaks fails the build | `CI` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

# [X03] Deployment artefacts: images, compose full, Helm, OpenTofu, serverless edges

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `deploy` |
| Priority | P1 |
| Depends on | [B05](B05-postgresql-repositories-schema-and-role-per-modu.md), [H01](H01-hutch-sim-as-an-http-service-with-http-drivers.md) |
| Plan | 21 §5, ADR-0016, ADR-0028 |
| Labels | `wave:w5`, `area:deploy`, `priority:p1`, `type:feature` |

## Context
No images or deployment files.

## Scope
- One OCI image per deployable; compose for `full`; Helm chart proven on kind in CI; OpenTofu reference
- Serverless packaging for verify, rendering, notifications, batch jobs

## Out of scope
- Running Kubernetes in development

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the Helm chart | installed on kind in CI | smoke tests pass | `CI` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Walkthrough WT-12 verified

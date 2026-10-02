# [H01] hutch-sim as an HTTP service with HTTP drivers

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `integration` |
| Priority | P1 |
| Depends on | [B07](B07-typed-settings-and-profile-wiring-no-environment.md) |
| Plan | 06 §9, 21 §2.3 |
| Labels | `wave:w4`, `area:integration`, `priority:p1`, `type:feature` |

## Context
Simulated HUTCH systems run in process; `/mock/*` routes live inside `/v1`.

## Scope
- `services/hutch-sim` serving the mock store; HTTP drivers for every port
- Read and command parity suites pass over HTTP
- Remove `/mock/*` from the Clarity API

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | each port | run against in-process and HTTP drivers | parity suites pass | `backend/tests/contract/test_port_parity.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Route contract and OpenAPI snapshot updated (routes removed)

# [F01] Foresight: backtest and calibration report

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `foresight` |
| Priority | P3 |
| Depends on | [AU01](AU01-autopsy-event-fed-embeddings-via-the-embed-role.md) |
| Plan | 02 §3.4 |
| Labels | `wave:w4`, `area:foresight`, `priority:p3`, `type:feature` |

## Context
Uncalibrated by design.

## Scope
- Backtest on historic launches (synthetic now); calibration report; still advisory only

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a backtest run | completed | the report states calibration error and that results are scenarios | `backend/tests/unit/test_autopsy_foresight.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

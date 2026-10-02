# [B08] Observability baseline: traces, metrics, masked logs, correlation IDs

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `platform` |
| Priority | P1 |
| Depends on | [B04](B04-outbox-in-the-unit-of-work-relay-and-consumer-fr.md) |
| Plan | 12 §25, 18 B11 |
| Labels | `wave:w0`, `area:platform`, `priority:p1`, `type:baseline` |

## Context
No tracing; logs are not structured.

## Scope
- OpenTelemetry SDK with console exporter (`lite`) and OTLP (`full`)
- Spans per HTTP request, module call and event; correlation ID propagated
- JSON logs with a PII-masking filter

## Out of scope
- Grafana dashboards (W5)

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | one confirm request | traced | one trace links HTTP, case, actions and the receipt consumer | `backend/tests/unit/test_tracing.py` |
| 2 | a log line containing an MSISDN | emitted | the number is masked | `backend/tests/unit/test_log_masking.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

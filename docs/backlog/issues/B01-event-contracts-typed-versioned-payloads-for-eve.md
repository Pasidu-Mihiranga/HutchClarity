# [B01] Event contracts: typed, versioned payloads for every catalogued event

| Field | Value |
|---|---|
| Wave | W0 Baseline wiring |
| Area | `platform` |
| Priority | P0 |
| Depends on | none |
| Plan | 21 §11.3, ADR-0029 |
| Labels | `wave:w0`, `area:platform`, `priority:p0`, `type:baseline` |

## Context
Events exist only as an envelope and a list of names in `platform/messaging/envelope.py`; payloads are untyped dicts, so producers and consumers cannot be checked against each other.

## Scope
- Add `clarity.contracts.events` with one Pydantic model per event marked 'exists' in 21 §11.3, named `type@v1`
- Payloads carry IDs, `Money` strings and hashes only; a schema test rejects fields that look like PII (msisdn, nic, name)
- Registry mapping event type to model; envelope validates `data` against it on publish

## Out of scope
- Kafka, schema registry (B03, B05)

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | an `action.completed@v1` payload with an extra `msisdn` field | it is validated | it is rejected | `backend/tests/contract/test_event_contracts.py` |
| 2 | every event type in the catalogue | the registry is loaded | each has exactly one model and a version | `backend/tests/contract/test_event_contracts.py` |
| 3 | a producer publishes an unknown event type | publish is called | it raises a typed error | `backend/tests/contract/test_event_contracts.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Event table in 21 §11.3 updated with schema links

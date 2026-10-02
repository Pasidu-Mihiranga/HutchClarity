# 2026-10-02 - B01 - Typed, versioned event contracts (#10)

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Anthropic), working with the team lead |
| Work package | B01, issue #10 (wave W0) |
| PR / commit | branch `feat/b01-event-contracts` |
| Units touched | contracts (new `events.py`), platform.messaging, tests |

## What changed
- `clarity.contracts.events`: `DomainEventType` (moved down from `platform.messaging`, alias kept), base `EventPayload`, 17 `...V1` payload models (IDs, `Money` strings, hashes, enums only), registry keyed by (type, version), `payload_model`, `validate_payload`, typed errors
- A payload class with a field named like personal data (msisdn, nic, name, ...) cannot be defined
- Envelope: `Event.of(payload, subject=...)`, `schema_id`, `payload()`, `caused(payload)`; `schema_version` is an integer
- Outbox validates on `append`, so malformed events fail at the producer
- Tests: shared sample payloads (`tests/support/events.py`); 41 contract tests including a check that plan 21 §11.3 and the code list the same events

## Decisions made
- Vocabulary lives in L0 (`contracts`) so producers in any layer and the platform can share it without an upward import
- Breaking change for event producers: `caused()` now takes a typed payload (only tests used it)

## Tests
- `make check`: ruff, ruff format, mypy --strict (107 files), 3 import contracts, 587 passed

## Next step
- B03 (#11) event bus port, then B04 (#12) outbox in the unit of work

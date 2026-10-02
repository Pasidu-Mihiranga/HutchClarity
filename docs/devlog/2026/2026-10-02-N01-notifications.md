# 2026-10-02 - N01 - Template-only notifications

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | N01 (#39), R6 |
| PR / commit | uncommitted |
| Units touched | notifications, app composition, persistence collections |

## What changed

- Added event consumers for receipt, risk and approval facts.
- Added approved template parameter contracts and explicit free-text refusal.
- Persisted recipient preferences, consent, quiet hours and delivery records.
- Added per-event idempotency, ordered channel fallback and delivery callbacks.

## Why

Issue N01 and ADR-0020 require notifications to be safe under event redelivery
and prevent generated or operator-supplied free text from reaching customers.

## Decisions made

- N01 dispatches template references and validated facts. Message wording stays
  outside the module and is supplied by approved channel templates.
- Provider-specific webhooks and real WhatsApp/SMS/USSD drivers remain N02.

## Docs updated

- [x] notifications `MODULE.md`
- [x] `docs/modules.md`, `ARCHITECTURE.md`
- [x] `CHANGELOG.md`, plan 21 status and plan revision record
- [ ] Walkthrough: no existing customer journey changed

## Tests

- Targeted notification, API, receipt-consumer, architecture and repository tests: passed.
- `mypy --strict`: passed (190 source files).
- `make check`: 1,214 passed, 512 infrastructure-dependent skipped; lint,
  formatting, strict typing and all three import contracts passed.

## Open issues / next step

N02 adds the external channel gateway and verified delivery webhooks after C01
is complete.

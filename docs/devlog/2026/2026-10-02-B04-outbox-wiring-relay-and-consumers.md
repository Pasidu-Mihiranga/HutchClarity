# 2026-10-02 - B04 - Outbox in the unit of work, relay, and consumer framework

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | B04 (issue #12), Wave 0 baseline wiring; plan 21 section 11.4, ADR-0014, ADR-0029 |
| PR / commit | issue #12, depends on #5 (B02) and #11 (B03), both merged |
| Units touched | platform/messaging (outbox rewritten; new `relay.py`, `consumers.py`, `correlation.py`) |

## What changed

- `outbox.py` rewritten as a **transactional** outbox. `outbox_in(unit)` returns an outbox backed by that unit of work's repository (B02), so an event is appended in the same transaction as the state change and commit stores both or neither. Rows carry status, attempts and the last error; `trace(correlation_id)` answers what one request caused.
- `relay.py` (new): reads committed pending rows, publishes to the bus (B03), then marks them sent. Deliberately in that order.
- `consumers.py` (new): the bookkeeping every at-least-once consumer needs, written once. `processed_event` per (group, event id), retry with doubling backoff, a dead-letter store, an alert hook, and per-group stats.
- `correlation.py` (new): a context variable bound around each handler call, so code that did not receive the event as an argument (a log formatter, a span exporter) can still see which request it belongs to.

The old `Outbox` conflated the outbox, the bus and the consumer framework. The bus moved out in B03; this change separates the other two.

## Why

Issue #12: the outbox existed but was wired to nothing. Without it, a state change and its event are two separate acts, and ADR-0014 exists because that is unsafe in both directions.

## Decisions made

- **Publish first, record sent second.** These cannot be atomic: the bus and the database are different systems. In this order the worst case is a duplicate; in the other order it is a lost event, which on `action.completed` means money moved and no receipt was ever issued. One duplicate is recoverable, one loss is not, so the relay always takes the duplicate. A test asserts the unsafe order fails.
- **A sent row is kept, not deleted**, so a relay restart is auditable.
- **A dead letter retires the event from the bus.** After the last attempt the wrapper returns normally instead of raising, because leaving a permanently broken event on the bus would block everything queued behind it for that subject. The event is in the dead-letter store, not lost.
- **A consumer of a critical event is refused at registration when no alert hook is configured.** This started as a default hook that raised when a critical event died, and the acceptance test showed why that is worse than useless: the bus reads any exception from a consumer as a delivery failure, so the alert was swallowed as a retry and nobody would have been told. Checking the wiring at registration fails while a developer is still looking at it rather than at 3am. `CRITICAL_EVENTS` in `envelope.py` is the list.
- **Backoff is a due time on the attempt record, not a sleep.** Drains are driven by the caller, so the wrapper refuses an event whose retry is not due (`EventIsInBackoff`) and the bus offers it again later. Nothing blocks a thread, and the test moves a fake clock instead of waiting.
- **The clock is injected** (`now: Callable[[], datetime]`), per I11, so backoff is tested exactly rather than approximately.

## Docs updated

- [x] MODULE.md of: no module changed; `platform` is a layer and has no MODULE.md
- [x] ARCHITECTURE.md: the Events row now describes the wired outbox, relay and consumer framework; `docs/modules.md` platform row updated
- [ ] Walkthrough: still no user-visible flow through this; B06 (#14) is the first real subscriber
- [ ] CHANGELOG.md / contracts: no `/v1` contract change; the OpenAPI snapshot is unchanged and green
- [ ] Plan via CHANGES.md: implements plan 21 section 11.4 as written, no plan change
- [ ] `.env.example`: no new variable

## Tests

- New `backend/tests/unit/test_outbox_wiring.py`: 18 tests, covering all three acceptance cases from the issue, plus per-group deduplication, backoff timing, the doubling schedule, correlation propagation and trace reassembly.
- `tests/contract/test_event_contracts.py` updated to the new outbox API; the round-trip and malformed-payload guarantees are unchanged.
- `tests/unit/test_events_and_audit.py`: the outbox section removed, because every test in it now has a better home. Checked one by one before deleting: delivery and dedupe to `test_outbox_wiring.py`, retry and dead-lettering to the acceptance tests there, failing-consumer isolation and per-subject ordering to the bus parity suite (B03), trace reassembly kept and moved. The file is now about the audit ledger only.
- `make check`: lint, format, `mypy --strict` (166 files), 3 import contracts kept, **633 passed, 13 skipped** (the skips are the Kafka parameter of the bus parity suite, which needs a broker).

Every acceptance test was verified to fail before the change, by breaking the specific mechanism it pins:

| Broken | Test that failed |
|---|---|
| outbox rows kept outside the unit of work | a rolled-back change publishes no event |
| `processed_event` lookup disabled | relay crash applies the event twice |
| relay marks sent before publishing | relay crash loses the event |
| exhaustion check removed | no dead letter, no alert, queue stays blocked |
| backoff doubling removed | retry gaps are not 2s, 4s, 8s |

## Open issues / next step

- B06 (#14) is the first real subscriber: receipts issued on `action.completed`. It is also the first code that will append to the outbox from inside a module's unit of work, which is the half of this work no production path exercises yet.
- Nothing calls `outbox_in` outside tests, so the seam is proven but unused. The composition root does not build a relay or a consumer registry yet; that belongs with B06 when there is something to subscribe.
- The dead-letter store has no replay path. Operationally a dead letter needs "fix the cause, then re-offer it"; that is worth its own issue.
- Backoff is per (group, event). A dependency that is down affects every event independently, so a broad outage produces many parallel retry schedules rather than one circuit breaker. Acceptable now, worth revisiting with X02 (#43).
- The relay is still called by hand. Running it as a process on a loop, and the ADR-0014 chaos test ("kill the relay mid-flight"), need the deployment work in X03 (#44) and X02 (#43).

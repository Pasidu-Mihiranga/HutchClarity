# 2026-10-02 - B03 - Event bus port with in-process and Kafka drivers

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | B03 (issue #11), Wave 0 baseline wiring; plan 21 section 11.4, ADR-0014, ADR-0027 |
| PR / commit | issue #11, depends on #10 (B01, merged) |
| Units touched | platform/messaging (new `bus.py`, `drivers/`), deploy (new), Makefile, plan 19 |

## What changed

- `platform/messaging/bus.py`: the `EventBus` port (`publish`, `subscribe`, `drain`, `close`) and `DeliveryReport`. Three documented guarantees: order per subject, at least once, and consumer groups that cannot affect each other.
- `drivers/in_process.py`: one FIFO queue per (consumer group, subject), standing in for a Kafka partition assigned to a group. A failure stops that subject's queue at its head, so a retry cannot reorder it.
- `drivers/kafka.py`: topic per event type, `subscriber_ref` as the key, consumer group per subscriber, auto-commit off, idempotent producer.
- `deploy/compose/full.yml` (new) and `make up-full` / `down-full` / `test-full`: Apache Kafka 4 in KRaft mode, so the DoD's "runnable via `make up-full`" is real rather than aspirational.
- `confluent-kafka` added as the optional `kafka` extra. `lite` still needs only Python.
- Plan 19 section 2.3.1 (new): the driver matrix built so far, how to run the `full` drivers, and the Kafka driver's design including where it differs from in-process.

`platform/messaging/outbox.py` was left alone. It is still unwired, and wiring it to this bus is B04 (#12).

## Why

Issue #11: there was no bus abstraction a module could publish to or subscribe on. ADR-0014 chose Kafka and ADR-0027 requires that a profile choose drivers, never seams, so the port has to exist before any module publishes an event.

## Decisions made

- **`drain()` rather than a background thread.** The relay decides when to deliver, so a test is deterministic and the in-process driver needs no thread. A real consumer process loops on `drain`.
- **A handler that raises means "not processed".** The bus re-offers the event. Retry backoff, the `processed_event` record and the dead-letter store are B04, deliberately not here: the bus's job is delivery, not the consumer's bookkeeping.
- **A failure blocks its own key and nothing else.** Skipping it would deliver a `receipt.issued` whose `action.completed` never arrived. The in-process driver blocks one subject; Kafka blocks the partition. Documented in both the driver docstring and plan 19 rather than smoothed over.
- **Subject-level failure isolation is tested per driver, not in the parity suite.** Only the in-process driver can promise it, so asserting it of every driver would have been a false contract. It lives in `tests/unit/test_in_process_bus.py`.
- **A new consumer group starts at the end of the log**, matching the in-process driver, and a restarting group resumes at its committed offset so nothing unprocessed is skipped.
- **confluent-kafka** (Apache-2.0 over librdkafka, BSD-2-Clause) as an optional extra. Both licences are OSI-approved and neutral, so I17 and plan 19 section 1 are satisfied; keeping it optional preserves ADR-0006.

## Docs updated

- [x] MODULE.md of: no module changed; `platform` has no MODULE.md (it is a layer, not a module)
- [x] ARCHITECTURE.md: messaging drivers listed; `docs/modules.md` platform row names the new ports and drivers
- [ ] Walkthrough: no user-visible flow changed yet; B04 and B06 bring the first event-driven flow
- [ ] CHANGELOG.md / contracts: no `/v1` contract change; the OpenAPI snapshot is unchanged and green
- [x] Plan via CHANGES.md: 19 section 2.3.1 added, recorded as plan v1.6 in `CHANGES.md` and the README revision table
- [x] `.env.example`: `CLARITY_KAFKA_BOOTSTRAP`

## Tests

- New `backend/tests/contract/test_bus_parity.py`: 13 tests, the contract both drivers must pass. Covers the issue's acceptance cases 1 (three events for one subscriber arrive in order) and 2 (a handler that fails once sees the event again and processes it once overall), plus per-subject rather than global order, group isolation, type filtering and the delivery report.
- New `backend/tests/unit/test_in_process_bus.py`: 6 tests for what that driver promises beyond the port.
- `make check`: lint, format, `mypy --strict` (163 files), 3 import contracts kept, **624 passed, 13 skipped**. The skips are the Kafka parameter of the parity suite, which needs a broker.
- **Acceptance case 3 verified for real.** Kafka was started with `make up-full` and the parity suite run against it: all 13 Kafka tests pass. The same suite, same assertions, both drivers.

The parity suite earned its keep: it caught four real bugs in the Kafka driver that no unit test would have found.
1. `subscribe` returned before the consumer group had joined, so every event published in the gap was lost. For `action.completed` that is a receipt that is never issued.
2. Waiting for partition assignment was still not enough, because a consumer resolves `latest` on its first fetch. The driver now pins each partition's start offset at subscribe time, and resumes a returning group from its committed offset instead.
3. `seek` was called with a `Message` where it needs a `TopicPartition`.
4. Rewinding a failed partition was not enough on its own: polling past the failure advanced the live position beyond the offset we had rewound to, so the failed event was never re-read. The driver now pauses the partition and rewinds it at the start of the next drain.

Each of those would have been an at-most-once bus that looked fine in `lite`.

## Open issues / next step

- B04 (#12) wires the outbox into the unit of work from B02 and publishes through this port, then adds the consumer framework: `processed_event`, retry with backoff, dead-letter store and the alert hook.
- B06 (#14) is the first real subscriber: receipts issued on `action.completed`.
- The Kafka driver is verified against a single-node dev broker with one partition in the parity suite. Multi-partition rebalancing, consumer restarts mid-flight and the chaos case in ADR-0014's compliance note ("kill the relay mid-flight") are B04 and X02 work.
- `make test-full` is wired but no CI lane runs it yet; that is B10 (#18).
- Unrelated finding: this repository's `.venv` holds two interpreters (`bin/python` is 3.12 while `bin/pip` installs into 3.14). Everything passes under both, but `make setup` should pin one. Worth a small issue.

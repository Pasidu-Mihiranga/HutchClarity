# 2026-10-02 - B06 - First event-driven flow: the receipt follows action.completed

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | B06 (issue #14), Wave 0 baseline wiring; plan 21 section 11.5, ADR-0029 |
| PR / commit | issue #14, depends on #10 (B01) and #12 (B04), both merged |
| Units touched | actions, case, receipts, app; platform/messaging (concurrency fix) |
| Review | money path (`modules/actions`, `modules/case`, `modules/receipts`): two approvals per AGENTS.md section 10 |

## What changed

- `actions`: `ToolLayer` takes a `UnitOfWorkFactory`. Completing a plan now writes the plan record and `action.completed@v1` in **one** transaction, so no interleaving shows a completed plan with no event (I7).
- `receipts`: `issue(plan_id=...)` is idempotent per plan, via a new `receipts.by_plan` index checked inside the service lock. `for_plan()` reads it back.
- `case`: `on_action_completed` is the consumer. After executing, `_execute` drains the relay and bus, then reads the receipt the event produced.
- **The per-plan lock is gone.** A caller that loses the race to confirm now finds the plan is no longer pending and joins the winner's outcome (`_join_original`) instead of failing or acting again.
- `app`: builds the bus, the relay and the consumer registry, and registers the receipts consumer. `deliver_events()` is the pump the case module calls.
- `platform/messaging/drivers/in_process.py`: concurrent drains are now safe (see below).

## Why

Issue #14 and plan 21 section 11.5: receipts were issued by a direct call inside the money path, with D1 held by a process-local lock. A lock cannot survive a second replica, and a side effect inside the request means a slow signer slows the refund.

## Decisions made

- **The consumer is `case`, not `receipts`.** The issue says "receipts consumes it", and that cannot be built as written. A receipt needs the evidence snapshot, the decision and the cause; ADR-0029 section 4 keeps all of that off the wire. So a consumer in `receipts` must call `case`, and `case -> receipts` already exists, which is a cycle that section 11.2 forbids. Fattening the event is what section 11.1 forbids. The consumer therefore lives in `case`, which is the orchestrator, and the `case -> receipts` edge is kept rather than removed. Raised with the maintainer before writing code and chosen deliberately; plan 21 section 11.5 and ADR-0029 both record the reasoning, and ADR-0029 now states the general rule: a consumer belongs in the module that orchestrates the reaction, not necessarily the one that owns the side effect.
- **Only the completion write became transactional.** Moving every `ToolLayer` write onto explicit units of work is most of M-ACT (#25), a Wave 1 money-path item. The completion write is the one that must be atomic with its event, so that is the one that changed.
- **`save` stays strict; a separate `_cache_outcome` tolerates a conflict.** `execution` and `receipts_by_plan` on the case record are a read cache of state `actions` and `receipts` own, and two confirmations of one plan necessarily compute identical values, so a conflict there is another thread writing the same thing. A conflict on `save` is a genuine lost update and still raises. Two methods rather than one tolerant method, so the distinction cannot be lost by accident.
- **A relay write conflict means "another relay got there first".** Nothing claims an outbox row before publishing: claiming would strand a row when a relay dies, and the design prefers a duplicate publish, which consumers deduplicate, over an event that is never published. The same applies to `processed_event` and the dead-letter write.

## Bugs this work exposed

The 1,500-confirm test found three real concurrency faults that the per-plan lock had been hiding. Each is a defect the lock masked rather than fixed, and each would have appeared the first time a second replica ran.

1. **The in-process bus was not safe for concurrent drains.** Two threads read `queue[0]`, both delivered the same event, and the second `popleft` hit an empty deque. Fixed with one lock per (consumer group, subject), which is the rule Kafka already applies: a partition is assigned to exactly one consumer in a group. Drains of different partitions still run in parallel; a drain of the same partition blocks, which is also what a caller reading the result of an event needs.
2. **The relay raced itself**, two threads marking the same outbox row sent. Now treated as the benign outcome it is.
3. **Two threads saved the same case record**, which optimistic concurrency correctly refused. Resolved by separating the strict write from the outcome cache, as above.

## Docs updated

- [x] MODULE.md of: case (events section, consumes), actions (events section, publishes), receipts (plan index)
- [x] Plan 21 section 11.2 (consumer placement), 11.3 (`action.completed` consumer), 11.5 (rewritten with what was built and why it differs)
- [x] ADR-0029: clarification on where a consumer may live
- [x] `plan.md`: B06 ticked
- [ ] ARCHITECTURE.md: no change needed; the Events row already describes the wired outbox, relay and consumer framework
- [ ] CHANGELOG.md / contracts: no `/v1` change. `ActionCompletedV1` was already defined by B01 and is unchanged; the OpenAPI snapshot test is green
- [ ] Walkthrough: the customer-visible flow is unchanged (same call, same response), so no walkthrough changed
- [ ] `.env.example`: no new variable

## Tests

- `tests/unit/test_migration_defects.py`: new `test_d1_fifteen_hundred_concurrent_confirms_give_one_refund_and_one_receipt`. 1,500 threads on one plan behind a barrier; asserts no errors, one distinct receipt, LKR 49.00 credited exactly once, and an intact receipt chain. Runs in about 3 seconds. The existing 60-iteration D1 tests are kept.
- `tests/unit/test_receipts_consumer.py` (new): 8 tests. Acceptance case 2 (delivered twice, one receipt) plus the same fact under a fresh event id, ten concurrent deliveries, and two tests pinning the payload: an exact key set, and no raw MSISDN anywhere in the serialised event.
- `make check`: lint, format, `mypy --strict` (166 files), 3 import contracts kept, module boundary and dependency map tests green, **642 passed, 13 skipped**. Acceptance case 3 (the R0 suite passes unchanged) holds.

Verified the 1,500-confirm test is not vacuous: with `_join_original` removed, 1,476 of 1,500 taps fail with `PlanNotPending`.

Honest limit on that test: the two per-plan guards, the one in `on_action_completed` and the one inside `ReceiptService.issue`, are redundant, and disabling either alone still passes. That is deliberate defence in depth on a money path, but it means the test pins the guarantee rather than each mechanism.

## Open issues / next step

- **The relay runs inline.** `deliver_events()` is called by the case module so a synchronous API can answer with what the event caused. A deployment should run the relay as its own process; that needs B10 (#18) and X03 (#44). Until then the receipt is still issued inside the request, so the latency benefit of this change is not yet realised, only its correctness and its shape.
- **`_join_original` polls with a 10 second ceiling.** The common case returns as soon as the winner's drain completes, because draining blocks on the partition. The poll covers the window where the winner has marked the plan completed in memory but has not yet committed its event. A durable claim that removes the window needs database row locks: M-ACT (#25).
- Still single-process: budget counters, confirmation tokens and OTP state remain in `DEFERRED` in `tests/architecture/test_module_state.py`, owned by M-ACT (#25) and M-IAM (#7).
- The flow is verified in `lite` only. `full` needs the Kafka relay process and the `make test-full` CI lane (B10).
- `reconciliation`, `insights` and `audit` are listed in plan 21 section 11.3 as consumers of `action.completed` and do not exist yet. The event they need is now published, so they are unblocked.

# 2026-10-03 - FIX - Three bugs behind one Kafka flake, one of them a lost event

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | Follow-up to C02 (#21): the full-lane flake recorded in its devlog |
| PR / commit | not committed at time of writing |
| Units touched | `platform.messaging.bus`, `platform.messaging.drivers.kafka`, `tests/contract`, `tests/unit`, `tests/integration` |

## What this started as

A flaky test. `test_bus_parity.py::test_a_blocked_event_clears_once_the_handler_recovers[kafka]`
failed in two of three `make test-full` runs and passed 26 of 26 times in
isolation. The A04 devlog had already noted a transient failure in the same
file and put it down to broker startup timing.

It was not timing noise. It was three separate bugs, and the test was right to
complain about the first of them:

1. A drain reported `is_clear` while a failed event was still undelivered.
2. The parity suite assumed one drain delivers everything just published, which
   only the in-process driver can promise. This was failing three runs in five.
3. **A consumer group that subscribes to a second event type lost events
   published afterwards, four times in five.** This one is not a test problem.
   It is the wiring `container.py` uses for `notifications` and `proactive`.

Only the first was visible from the flake. The second showed up once the first
was fixed, and the third was hiding behind both.

## The bug

`DeliveryReport.is_clear` means "nothing failed and nothing is waiting behind a
failure". A drain could return it while a failed event was still undelivered.

The mechanism. When a handler raises, `_block` pauses that partition at the
failed offset and does not commit. The next drain calls `_rewind_blocked`, which
resumes the partition and seeks back to that offset, then polls. **`seek` is
asynchronous**: it throws away the local fetch queue, and refilling it is a
round trip to the broker. So the first poll after a rewind can legitimately
return nothing while the retried message is still in flight.

`_drain_group` treated that empty poll as "idle" and returned
`delivered=0, failed=0, stalled={}`. A relay reading that report would believe
everything was delivered. The driver's one promise, that a failure delays
delivery and never drops it, was not held by the value it reports.

The 0.5 s default poll usually covered the round trip, which is why this looked
like a flake rather than a bug.

**Reproduced deterministically** by shrinking the poll window below a round
trip, which turns the race into a certainty:

```
poll=0.5   first=1 second_clear=True delivered=1 seen=1 ok
poll=0.05  first=1 second_clear=True delivered=0 seen=0 BUG: clear but undelivered
poll=0.01  first=1 second_clear=True delivered=0 seen=0 BUG: clear but undelivered
```

## The fix

Stop guessing what "idle" means and ask the broker. `publish` already flushes,
so anything published before a drain started is durable and the partition's high
watermark says how far it reaches. On every **empty** poll the drain compares
that watermark against how far it has read, and keeps polling while either a
rewound partition or an unread offset is outstanding, bounded by a new
`rewind_grace_seconds` (default 15 s). A rewound partition still outstanding
when the grace runs out is put back in `_blocked`, so the report says "stalled"
rather than "all clear".

## Two things I got wrong on the way, both measured

**1. The obvious implementation made drains 7x slower.** My first version read
the watermark with `cached=False` and the group position with `committed()`,
once per partition per drain. Measured:

| | idle drain, 1 partition | idle drain, 6 partitions |
|---|---|---|
| before | 0.52 s | 0.52 s |
| live watermark + `committed()` | 1.01 s | **3.51 s** |
| cached watermark + in-memory position | 0.52 s | 0.52 s |

An uncached `get_watermark_offsets` costs about **515 ms**; the cached read
costs **0.01 ms** and already knew about six freshly published messages before
the first poll. So the watermark comes from librdkafka's cache, which every
fetch response updates, and the position is tracked in memory as the driver
commits rather than asked of the coordinator. `_pin_start` already resolves the
starting offset, so that is the one place that pays for it.

**2. I introduced a 15 second stall on every drain.** With the watermark check
in place, a partition blocked behind a failing handler is paused and produces
nothing, so the drain waited the entire grace for it, every time:

```
drain 1:  15.1s failed=1 stalled=True
drain 2:  15.5s failed=1 stalled=True
```

With a down adapter, every relay tick would have taken 15 s. Caught by timing
the obvious scenario rather than by a test, and it also showed up as the full
lane taking 209 s instead of 99 s. Paused partitions are now excluded from the
outstanding set, since `awaiting` and `_blocked` already track them with their
own deadline:

```
drain 1:  0.5s failed=1 stalled=True
drain 2:  1.0s failed=1 stalled=True
```

## A second, unrelated flake in the same lane

`test_two_replicas.py::test_two_processes_each_plan_is_claimed_exactly_once`
also failed intermittently, and for a different reason: its own non-vacuity
guard was racy. Both replicas claim `PLAN-0000..0499` in the same order, so if
the first process spawned got far enough ahead it claimed all 500 and the
second claimed none, failing `"one replica claimed nothing, so there was no
contention"`.

The substantive assertions (no plan claimed twice, every plan claimed once, the
database agrees) were never in doubt. The guard was checking something real and
checking it by hope. The workers now meet at a barrier in the database before
claiming, so contention is arranged rather than wished for. 0 failures in 8
runs.

## Broker hygiene, which was making all of this worse

The Kafka parity fixture takes a fresh topic prefix per test and leaves the
topics behind, deliberately: "a dev broker is disposable". After this session's
work the local broker held **490 topics and 410 consumer groups**, all test
scratch. That is metadata and coordinator load on every assignment and fetch,
and it widens exactly the timing window this bug lived in.

Cleared by hand, which is part of why the later measurements are cleaner than
the earlier ones. I have **not** added automatic deletion to the fixture: it
would mean test code deleting broker state on every run, and the leave-behind is
a deliberate choice by whoever wrote the fixture. `make down-full` does it
wholesale. Worth a decision rather than a quiet change.

## The second bug, which the first one was hiding

With the redelivery bug fixed, five full-lane runs failed three times, on
**three different tests**:

```
run 1  -
run 2  FAILED test_the_report_counts_handler_calls[kafka]
run 3  -
run 4  FAILED test_order_is_per_subject_not_global[kafka]
run 5  FAILED test_three_events_for_one_subscriber_arrive_in_order[kafka]
```

Three names, one shape: publish, drain **once**, expect everything. That is not
a flaky test either. It is the parity suite asserting a property the port never
promised and only one driver has.

The in-process driver keeps its queue in memory, so one drain after a publish
delivers it. Kafka fetches, and a fetch is a round trip, so an event that is
already published and durable may simply not be in hand yet; that drain
honestly reports nothing and the next one delivers. The port's three guarantees
(order per subject, at least once, order survives failure) are all about *what*
is delivered and none of them is a timing claim. Only `drain`'s own docstring
made one, "returns once there is nothing deliverable left", and for a networked
driver that cannot be known without paying a round trip per partition.

So all sixteen `drain()` calls in the suite were testing in-process timing, and
the Kafka driver was being failed for not being in-process.

### How this was decided, because the previous version of this entry asked

I had written the options up as **(A)** relax the port's promise and drain until
quiet, or **(B)** pay the live watermark (about 515 ms per partition per drain,
measured above), and said both wanted an owner and probably an ADR.

No ADR is needed, because the suite's own docstring already decided it. It says:

> Both honour the port, so the narrower in-process promise is tested in
> `tests/unit/test_in_process_bus.py` instead of being asserted of every driver.

That rule was written for how widely one failure spreads (in-process blocks one
subject, Kafka blocks a partition). "One drain is enough" is the same kind of
promise for the same reason, so it gets the same treatment rather than a new
decision. **(A)**, by the rule already in the file.

(B) was also the wrong trade on its own terms: it would slow every relay tick in
production to make a test suite greener, and still only narrows the window,
since `publish` flushing does not put the record in *this* consumer's fetch
queue.

### What changed

- **`EventBus.drain` says what it does.** It offers what has *arrived*; how much
  has arrived is not part of the contract; a later drain offers the rest. A
  relay must never read one quiet drain as "the backlog is empty", which is the
  same mistake the driver itself was making.
- **The parity suite drains deliberately.** Two helpers, because the sixteen
  calls were making two different claims that one `drain()` had conflated:
  - `deliver(bus, expect=n)` drains until quiet, for the tests whose claim is
    *what* was delivered (order, group isolation, delivery counts). Quiet means
    **two** consecutive empty drains, not one: a single empty fetch is precisely
    what the driver used to misread, and the helper must not reintroduce that
    bug on the test side. A reached deadline fails, naming what was missing.
  - `until_failed(bus)` drains until one drain saw the failure and returns
    *that* drain's report untouched, for the tests whose claim is a failure
    boundary ("the first offer failed", "nothing came past the blocked one").
    Draining until quiet there would perform the retry inside the helper and
    assert nothing. It waits for the failure specifically rather than for any
    delivery, because in the two-group test the healthy group satisfies "a
    handler ran" on its own while the failing group has not fetched yet.
- **The in-process promise moved to the in-process tests**, where it is true and
  where losing it would be a real regression:
  `test_one_drain_delivers_everything_already_published`.

Order, at-least-once and group isolation are all still asserted of both drivers,
unchanged. What the suite stopped asserting is a timing property that was never
a guarantee.

## The third bug, and the one that would have bitten production

Fixing the suite left one test still failing about one run in ten, and it was
the only one that failed for a reason the suite was right about:
`test_two_handlers_in_one_group_count_as_one_delivery`. Not a fetch race. The
event never arrived at all, through twenty seconds of draining.

It is also the only parity test that calls `subscribe` **twice for one group**,
which turned out to be the whole story.

`subscribe` called `consumer.subscribe(topics)` and then `_pin_start` every
time. Re-subscribing triggers a **rebalance**, and `_await_assignment` decided
the rebalance was done by looking at `consumer.assignment()`, which reads as
satisfied while one is still in flight. So the `seek` landed on a partition
about to be revoked, went away with it, and the consumer fell back to resolving
`auto.offset.reset=latest` on its own at *fetch* time, which is after the
publish. The event was not delayed, it was skipped, permanently.

That is the exact promise `_await_assignment` existed to keep, in its own
docstring: "nothing published after subscribe is lost".

**Measured with a probe** rather than inferred, five rounds of three cases:

```
one subscribe (control)                delivered=1 seen=1 ok
second subscribe, same type            delivered=1 seen=2 ok
second subscribe, new type             delivered=0 seen=0 LOST   <- 4 of 5
```

The same-type case is the one the parity test hits, and it loses occasionally.
The **new-type** case loses four times in five, and that is the one that
matters, because it is the ordinary wiring: a consumer group that handles
several event types subscribes once per type. `container.py` does it in a loop
for `notifications` and `proactive`. In the `full` profile those two groups
could silently drop anything published between their first and last subscribe.

### The fix

Pin in the rebalance callback, which is the only place an offset choice sticks.
`consumer.subscribe(topics, on_assign=...)`, and the callback sets each
partition's offset and calls `assign`, in this order of preference:

1. **A partition this driver already tracked**: resume exactly where it was.
   This is the case the old code got wrong, and it is what makes adding a topic
   stop disturbing the topics a group already had.
2. **Blocked behind a failed handler**: resume at the failed offset, so a
   rebalance cannot turn a retry into a skip.
3. **New to this group**: its committed offset if it has one, else the end of
   the log, as before.

Two smaller things fall out of it. `_await_assignment` now waits for the
callback to have fired rather than for `assignment()` to look right. And a
second handler for a type the group already has returns immediately without
touching the broker, because re-subscribing to an identical topic list buys a
rebalance for nothing.

**Verified both ways.** With the fix, 15 of 15 probe rounds clean. The new
parity test, `test_a_group_adding_a_second_type_does_not_lose_the_first`, fails
3 of 3 against the old behaviour and belongs in the shared suite rather than the
Kafka file, because "nothing published after subscribe is lost" is the port's
promise and not this driver's favour.

## A documentation bug found on the way

Writing `expect=` on each call meant predicting `delivered`, which turned up a
disagreement between the port and both drivers. `DeliveryReport.delivered` was
documented as "handler calls that returned without raising". Neither driver
counts that: both increment once per event per **group**, however many handlers
the group has. `failed` likewise counts blocked subjects per group, not raises.

The drivers agree with each other, so the documentation was the wrong one, and
it is the kind of wrong that matters: `delivered` is what a relay logs. Both
field docstrings now say what is counted and what is not.

It had never been contradicted because `test_the_report_counts_handler_calls`
used one handler per group, where the two numbers coincide. Renamed to
`test_the_report_counts_one_delivery_per_event_per_group`, and
`test_two_handlers_in_one_group_both_run` is now
`test_two_handlers_in_one_group_count_as_one_delivery` and asserts the count
that tells the two readings apart.

## Docs updated

- This devlog.
- No `MODULE.md` change: `platform.messaging` has no module file (it is L2, not
  a domain module).
- `CHANGELOG.md`: the port's documented promise changed, which is a public
  surface change even though no signature moved. `KafkaEventBus` also gained an
  optional `rewind_grace_seconds`.
- No `.env.example` change: not configurable by environment.

## Tests run

- New: `tests/contract/test_kafka_redelivery.py`, six tests. Three of them fail
  against the unfixed driver, deterministically, because they shrink the poll
  window instead of waiting for load to lose the race. One of the six exists
  only to stop the fix being "wait longer everywhere": it asserts an idle drain
  still returns in under a second.
- New: `test_a_group_adding_a_second_type_does_not_lose_the_first` in the parity
  suite. Fails 3 of 3 against the old subscribe path.
- New: `test_one_drain_delivers_everything_already_published` in
  `tests/unit/test_in_process_bus.py`, holding the promise the parity suite
  stopped asserting of every driver.
- `make check`: **1469 passed, 534 skipped** (1467 and 533 before this change,
  which accounts for exactly the three tests added).
- Non-vacuity, three probes, each failing exactly what it should:
  - a driver that delivers **one event per drain** (a correct but slow driver)
    passes the parity suite, which is the point of the change, and fails
    `test_one_drain_delivers_everything_already_published`, which is where that
    promise now lives.
  - a driver that **silently drops** every other event fails three parity
    tests, including both ordering tests, so `deliver` has not made the suite
    vacuous.
  - the old subscribe path fails the new subscribe test 3 of 3.
- `tests/integration/test_two_replicas.py`: 0 failures in 8 runs.
- The lane the whole exercise started from, `test_bus_parity.py` plus
  `test_kafka_redelivery.py` against a real broker, **5 clean runs of 34 tests**
  at 93 s each. The same measurement before this change was 3 failures in 5
  runs, on three different tests.

## Next step

Back to C03 (#22), the bounded agent step.

Still open, and deliberately not changed here: the Kafka parity fixture leaves
its topics behind (see above). That is a fixture policy question, not part of
this fix.

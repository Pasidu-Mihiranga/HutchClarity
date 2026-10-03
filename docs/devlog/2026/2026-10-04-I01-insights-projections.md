# 2026-10-04 - I01 - Insights, and a float on a money path

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | I01 (`docs/backlog/issues/I01-insights-projections-and-console-dashboards.md`, #30), Wave 4 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.insights` (`projections.py`, `service.py`, `public.py`), `app` (`container`, `collections`), `interfaces.http` |

## What changed

`insights` was a scaffold. It now has:

- **`projections.py`**: the read model as a pure fold over events, with the
  four dashboards as views over it.
- **`service.py`**: `InsightsService`, which consumes events, keeps the
  projection in a repository and can rebuild it from a log.
- `GET /v1/demo/ops` served by the projection instead of by live objects.

## The property, and the three things that give it

Acceptance 1 is "replaying the event log rebuilds the same numbers". That is
not a nice-to-have: a read model is a cache of the log, and a cache that
disagrees with its source is worse than no cache, because somebody acts on it.

Three rules get it, and each is a thing projections usually get wrong:

1. **Folding an event twice counts it once.** Consumers are at-least-once
   (I7), so a redelivery is normal rather than exceptional. Every event id the
   fold has seen is kept and a repeat is a no-op. Without this the first
   redelivery silently inflates a dashboard and nothing says it happened.
2. **Joins happen at read time, not at apply time.** "Refunds by rule" needs a
   case's cause and its refunds, which arrive in separate events with no
   guaranteed order across partitions. A fold that joined on arrival would drop
   a refund whose `cause.detected` had not landed, and the total would depend
   on delivery order. So the fold keeps per-case facts and the view joins them.
   `test_a_refund_arriving_before_its_cause_is_still_attributed` is the one
   that would fail if somebody moved the join.
3. **Anything "latest" is decided by a number in the event, never by arrival
   order.** The last state a conversation reached is the turn with the highest
   `turn_no`. Otherwise a replay in a different order gives a different answer,
   which is exactly what acceptance 1 forbids.

So the suite asserts more than the issue asks for. Acceptance 1 compares a
replay to an incremental fold; the stronger test shuffles the log and compares
again, because a replay happens to be in log order while a *consumer* sees
whatever order delivery gives it. A projection that agreed only in log order
would drift in production and pass in the test.

## The float

The route I replaced did this:

```python
money = 0.0
for record in records:
    stake = record.case.money_at_stake_lkr
    if stake is not None:
        money += float(stake)
...
"money_at_stake_lkr": f"{money:.2f}",
```

I3 is "Money is `Money` (Decimal, LKR). No floats anywhere on a money path",
and a dashboard is on one: a figure a desk acts on has to be the figure the
ledger holds, and `f"{money:.2f}"` hides the drift rather than preventing it.
The projection keeps `Decimal` throughout and serialises as a string.

Worth being clear that this was pre-existing and in a `tags=["demo"]` route,
so nothing was wrong in production. It was still the only arithmetic on money
outside the money path, and it is gone.

## A bug the real-log test found

I wrote `test_the_real_event_log_rebuilds_to_the_same_dashboards` because the
crafted log proves the fold is deterministic and proves nothing about whether
the system's real events carry what the dashboards read: a projection can be
perfectly deterministic over a log whose fields it never populates, and every
number would be zero.

It failed, and for a reason worth keeping:

```
{'events_folded': 14} != {'events_folded': 9}
```

Every dashboard figure agreed. Only the counter differed, because a rebuild
folds the **whole** log while the consumer group receives only the types it
subscribed to. `events_folded` was counting events the projection ignored.

Two ways to fix it, and the lazy one is to filter the log in `rebuild`. The
honest one is that a counter called "events folded" should mean the events the
projection *used*: a dashboard claiming 14 when it used 9 is misleading on its
own terms. So an event of an unread type is now neither counted nor recorded,
and the property holds whatever else is in the log.

That also produced `PROJECTED`, one tuple of the payload types the fold reads,
which the container derives `INSIGHT_EVENTS` from. A type folded but not
subscribed makes a live projection disagree with a replay, and a type
subscribed but not folded wastes deliveries; deriving one from the other makes
both impossible.

## Metric definitions that are easy to fake

**A handoff is not a drop-off.** Counting every conversation that did not reach
`answered` would include the ones correctly handed to a person, which are
resolutions of a different kind, and the drop-off rate would look worse the
better the handoff worked. Terminal states are terminal, and only the rest
count.

**"Where AI stops" is per reason, not one number.** A refusal is a safety
control doing its job, a verifier failure is the assistant nearly saying
something wrong, and a handoff is a customer who asked for a person. One
combined figure cannot tell them apart and they call for different work.

**A refund with no known cause is reported, not dropped.** Money that moved and
cannot be explained is the most important row on that dashboard, not the one
to hide, and dropping it would make the total disagree with the ledger.

**A share of nothing is `None`, not zero.** An empty dashboard reading "0%"
looks like a measurement.

**A cause carries its rule version.** `VAS_NO_CONSENT@3` and `@4` are different
logic, and merging them would hide the effect of publishing one.

## Contract and plan notes

- **No new event.** Insights consumes seven existing types and produces none: a
  read model that emitted events would be a read model something else depended
  on, which is the opposite of what it is for.
- **No new module edge.** `"insights": set()` holds. Insights is event-fed by
  design, which is ADR-0029 exactly: it reacts to facts and never asks a module
  a question.
- **The OpenAPI snapshot changed**, because `/v1/demo/ops` returns the
  dashboards rather than the old counts. A demo route behind
  `DESK_QUEUE_READ` with no frontend consumer, so this is deliberate.
- Collection `insights.projections` registered.

## Docs updated

- This devlog, `backend/src/clarity/modules/insights/MODULE.md` (replacing the
  scaffold stub), `CHANGELOG.md`, `ARCHITECTURE.md`, `docs/modules.md`,
  `plan.md` (#30 ticked).

## Tests run

- `make check`: **1745 passed, 544 skipped** (1727 before I01).
- `backend/tests/unit/test_insights.py`, 18 tests.
- Acceptance 1 three ways: a replay matches an incremental fold, a rebuild
  through the stored service matches what it folded live, and a rebuild from
  the **real** event log the system produced matches the live dashboards.
- Order independence on a shuffled log; idempotency for the whole log and for
  one redelivered event.
- The four dashboards, including the definitions above.
- That `projections.py` imports no clock, no persistence and no randomness,
  checked by parsing the module: an import added later would be invisible in a
  behaviour test until a rebuild disagreed.
- Non-vacuity, two probes: removing the seen set fails the two idempotency
  tests; dropping unattributed refunds fails the unexplained-refund test and
  the Decimal test.

## Known gaps

- **The console renders none of it.** `GET /v1/demo/ops` is the only surface
  and it is a demo route. That is the next piece of work and the same gap AU01
  and D01 carry.
- **The projection has no offset of its own.** The `seen` set grows with the
  log, which is the honest trade for a prototype; B04's `processed_event`
  record is where a per-consumer offset belongs once insights is a deployable
  of its own. Until then a long-lived process holds every event id it has
  folded.
- **`ENDINGS` duplicates flow state names** that `config/flows/*.yaml` owns, so
  a renamed state silently turns every conversation through it into a
  drop-off. Same class of duplication as K02's `TOOL_ARGS` and C05's
  `FLOW_STEPS`, and it wants the same fix: serve the flow's terminal states
  from one place.
- No time dimension. Every dashboard is "since the beginning of this log", so
  there is no trend, no per-day figure and no window. A real console wants all
  three, and that needs the event's own timestamp folded into buckets rather
  than a new data source.

## Next step

The console surfaces for the three modules built without one (AU01, D01, I01),
or the remaining Wave 4 items. The cross-cutting gaps are unchanged: an
embedding model (K02, K03, AU01), a recorded cassette (C03, C04, K03), and
publishing content artefacts through `PolicyGovernance` (C02, K01, AU01).

# insights - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.insights`) |
| Deployable | `clarity-api` today (modular monolith); a candidate for extraction |
| Owner | TBD |
| Status | built (`lite` and `full`): event-fed read models, I01 (#30), 2026-10-04 |
| Files | `projections.py`, `service.py`, `public.py` |

## 1. Purpose

The console's numbers: top causes, where the assistant stops, drop-offs and
refunds by rule (plan 02 section 3.5, plan 10).

Read models folded from the event log, not read from live objects. The
difference is the point: a projection survives a restart, two replicas agree,
and replaying the log rebuilds exactly the same numbers.

## 2. Public surface (`public.py`)

`InsightsService`, `Insights`, `CaseFact`, `TurnFact`, `apply`, `rebuild`,
`PROJECTED`, `PROJECTIONS`, `CURRENT`, `ENDINGS`, `STOP_REASONS`.

`projections.py` is pure: it reads no clock, no repository and no other module,
because a projection that consulted anything outside its events could not be
rebuilt from them. `test_the_projection_reads_nothing_but_its_events` parses
the module and asserts it.

## 3. Used by

`clarity.app.container`, which constructs the service and registers it as the
`insights` consumer group; and `clarity.interfaces.http` for
`GET /v1/ops/summary`.

## 4. Depends on

| Package | Through |
|---|---|
| `clarity.contracts.events` | the payload types it folds |
| `clarity.platform.messaging.envelope` | `Event` |
| `clarity.platform.persistence` | `Repository`, `UnitOfWork`, `UnitOfWorkFactory`, `MemoryStore` (service only) |

No synchronous call to another module (`"insights": set()` in
`tests/architecture/test_module_dependencies.py`). Insights is event-fed by
design: it reacts to facts and never asks a module a question (I22, ADR-0029).

## 5. Data owned

`insights.projections`: one row, holding the whole read model. A read model is
one value rather than a table of them, and it is a cache of the log, so the log
stays the authority and `rebuild_from` is how the cache is made to agree again.

## 6. Invariants

- **Replaying the log rebuilds the same numbers.** The property the whole
  module exists for, and acceptance 1.
- **Folding an event twice counts it once.** Consumers are at-least-once (I7),
  so a redelivery is normal; without the seen set the first one silently
  inflates a dashboard and nothing says so.
- **Joins happen at read time, never at apply time.** A case's cause and its
  refunds arrive in separate events with no guaranteed order, so joining on
  arrival would drop a refund whose cause had not landed and the total would
  depend on delivery order.
- **Anything "latest" is decided by a number in the event**, not by arrival
  order: the last state a conversation reached is the turn with the highest
  `turn_no`.
- **The subscription is derived from the fold.** `INSIGHT_EVENTS` in the
  container is built from `PROJECTED`, so a type folded but not subscribed (or
  the reverse) is impossible.
- **Money stays `Decimal`** and serialises as a string (I3). The route this
  replaced summed with `float`.
- **A refund with no known cause is reported, not dropped.** Money that moved
  and cannot be explained is the most important row on that dashboard.
- **A handoff is not a drop-off.** A customer with a person is a resolution of
  a different kind, and counting it as abandonment would make the metric
  flatter.
- **A share of nothing is `None`, not 0.** An empty dashboard must read as "no
  data" rather than as a real zero.

## 7. Migration status (enterprise-plan 21)

R6. The projections, the consumer and the persistence are in place.

**Not yet:** the console does not render any of it, so `GET /v1/ops/summary` is
the only surface and it is a demo route. The projection also has no offset of
its own: the `seen` set grows with the log, which is the honest trade for a
prototype, and B04's `processed_event` record is where a per-consumer offset
belongs once insights is a deployable of its own.

`ENDINGS` is a second copy of flow state names that `config/flows/*.yaml` owns.
A renamed state silently turns every conversation through it into a drop-off.
Serving the flow's terminal states from one place is the fix, and it is the
same class of duplication K02's `TOOL_ARGS` and C05's `FLOW_STEPS` have.

## 8. Events

Consumed, through the `insights` group: `case.created`, `cause.detected`,
`decision.generated`, `action.completed`, `action.failed`, `receipt.issued`,
`conversation.turn.completed`.

None produced. A read model that emitted events would be a read model
something else depended on, which is the opposite of what it is for.

## 9. Tests

- `backend/tests/unit/test_insights.py` - replay determinism (I01 acceptance
  1), order independence, idempotency, the four dashboards, that the module is
  pure, and a rebuild from the real event log the system produced

## 10. Change history

| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-dev-merge.md` | Scaffold: `public.py` and `MODULE.md` stubs to satisfy the architecture tests |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-I01-insights-projections.md` | Event-fed read models, replay determinism, and `/v1/ops/summary` off live objects |

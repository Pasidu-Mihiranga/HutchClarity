# proactive - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.proactive`) |
| Deployable | `clarity-stream` target; in-process worker today |
| Owner | TBD |
| Status | built (P01) |
| Backlog | `docs/backlog/issues/P01-proactive-module-stream-detectors-and-risk-detec.md` |

## 1. Purpose

Consume system-recorded payment, usage and pack events, recognize configured
risk patterns, and publish evidence-backed `risk.detected` facts. The module
does not decide outcomes, open cases, execute actions or generate customer
wording.

## 2. Public surface (`public.py`)

- `ProactiveService.consume_event`
- `SignalRecord`, `RiskRecord`
- owned collections `SIGNALS`, `RISKS`
- `CONSUMED_EVENTS`, used by the composition root for subscriptions

## 3. Used by

`clarity.app` registers the stream consumers. The composition root reacts to a
duplicate-reload risk by calling the existing resolution flow, which remains
the only path that detects a cause, decides an outcome and executes an action.

## 4. Depends on

| Package | Through |
|---|---|
| `clarity.contracts.events` | typed payment, usage, pack and risk payloads |
| `clarity.platform.config` | effective-dated detector parameters |
| `clarity.platform.messaging` | event envelopes and transactional outbox |
| `clarity.platform.persistence` | owned signal and risk records |

No synchronous module dependency is added.

## 5. Data owned

- `proactive.signals`: idempotency and recent evidence for ingested facts
- `proactive.risks`: one record per stable risk key

Records contain pseudonymous subscriber references and system evidence
references, never raw customer identifiers or customer text.

## 6. Invariants

- Risks are derived only from typed system facts, never customer text.
- A redelivered source event cannot create a second signal or risk.
- A stable risk key cannot publish `risk.detected` twice.
- Windows and FUP warning thresholds resolve from policy as of the source fact.
- Event time comes from the source event; domain code does not read wall time.
- The module never chooses an outcome or executes an action.

## 7. Events

Consumes `payment.recorded@v1`, `usage.threshold_reached@v1` and
`pack.expiring@v1`. Publishes `risk.detected@v1` through the same unit of work
that stores the risk.

## 8. Config keys

| Key | Type | Initial value | Owner |
|---|---|---|---|
| `detection.duplicate_reload.window` | duration | `PT30M` | risk |
| `proactive.fup.warning_thresholds` | string list | `80,95` | product |

Initial values are assumptions and require HUTCH validation.

## 9. Failure modes

Invalid or missing policy stops the consumer, leaving the event available for
the consumer framework's retry and dead-letter path. A failed unit of work
stores neither the risk nor its event.

## 10. Tests

- `tests/unit/test_proactive.py`: detector policy, deduplication and events
- `tests/acceptance/test_zero_contact.py`: two captures and one credit produce
  one AUTO_FIX case, action and receipt without human input
- `tests/contract/test_repository_parity.py`: collections exist in both stores

## 11. Change history

| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-P01-proactive-detectors.md` | Event-fed duplicate reload, FUP and pack-end detectors with zero-contact resolution (P01) |
| 2026-10-02 | - | Scaffold created |

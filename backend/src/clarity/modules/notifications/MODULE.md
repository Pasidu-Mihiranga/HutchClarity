# notifications - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.notifications`) |
| Deployable | `clarity-worker` today; extractable fan-out service later |
| Owner | TBD |
| Status | built (N01) |
| Backlog | `docs/backlog/issues/N01-notifications-module-templates-preferences-conse.md` |

## 1. Purpose

Route notification-worthy facts through customer or staff preferences,
consent, quiet hours, approved template parameters, channel fallback and
delivery tracking.

## 2. Public surface (`public.py`)

- `NotificationService`, `NotificationRequest`, `NotificationRecord`
- `RecipientPreference`, `Purpose`, `DeliveryStatus`
- `MemoryNotificationDispatcher` (labelled simulated driver)
- `NotificationRefused`, `DispatchFailed`
- owned collections `NOTIFICATIONS`, `PREFERENCES`

## 3. Used by

`clarity.app` registers the event consumers and selects the dispatch driver.

## 4. Depends on

| Package | Through |
|---|---|
| `clarity.contracts.events` | typed receipt, risk and approval payloads |
| `clarity.platform.messaging` | event envelope and at-least-once consumer framework |
| `clarity.platform.persistence` | owned preferences and delivery records |

No synchronous module dependency is added.

## 5. Data owned

- `notifications.preferences`: language, channel order, consent and quiet hours
- `notifications.records`: one record per `(event, recipient, template)`

## 6. Invariants

- Free text is refused. Only registered template IDs with exact parameters dispatch.
- A redelivered event cannot send a second message.
- Consent and quiet hours are evaluated before dispatch.
- A failed preferred channel falls through to the next configured channel.
- All time comes from the injected clock.

## 7. Events

Consumes `receipt.issued@v1`, `risk.detected@v1` and
`approval.requested@v1`. It publishes no event yet; N02 supplies provider
callbacks and the channel gateway.

## 8. Tests

- `tests/unit/test_notifications.py`
- `tests/unit/test_receipts_consumer.py` (receipt event chain)
- `tests/contract/test_repository_parity.py` (owned collections)

## 9. Change history

| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-N01-notifications.md` | Templates, preference/consent routing, idempotency, fallback and delivery status (N01) |
| 2026-10-02 | - | Scaffold created |

# 2026-10-05 - E3 - Handoffs reach the desk; the receipt link opens

Written by an AI coding agent (Claude Code) for its own change.

## What changed

- `conversation.turn.completed@v1` carries optional `handoff_queue` and
  `handoff_reason` (stable codes). The turn record keeps both.
- Resolution consumes the event (group `case-handoff`): a handed-off turn
  records a `HandoffRequest` on the case, and `GET /v1/desk/queue` lists any
  open case with one, with the reason "Handed off by the assistant (...) to
  <queue>". No `/v1` schema change: the queue row's existing `reason` field.
- The conversation routes (HTTP and channel gateway) deliver events after a
  turn. No relay process runs beside the API on the VPS, so turn events (and
  the insights projections fed by them) waited until an unrelated execution
  drained the outbox.
- Customer web: the receipt id is read from `payload.receipt_id` of the
  signed document (`receiptIdOf`). "View Trust Receipt" did nothing and the
  receipt card showed "-", because both read a top-level id that the
  envelope does not have.

## Why

Live: the assistant told a customer their case went to `cx-knowledge`, and
the desk never showed it. The handoff existed only in the chat reply.

## Validation

- New API test: a "talk to a human agent" turn puts the case on the desk.
- Full backend suite, ruff, mypy: see the PR.
- customer-web tsc: clean.

## Next step

A desk action to close a handoff (today it stays listed until the case
closes).

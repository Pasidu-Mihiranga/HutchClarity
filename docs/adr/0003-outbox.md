# 0003 - Transactional outbox for events

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
Money-moving side effects must not be lost or duplicated. Dual writes to DB + bus are unsafe.

## Decision
State change and event share one Postgres transaction (outbox). A relay publishes to `InMemoryBus` (lite) or Kafka KRaft (full). Consumers are idempotent via `processed_event` with DLQ on repeated failure.

## Consequences
Chaos tests kill the relay mid-flight and assert no lost or duplicate side effects. Business code never publishes directly to Kafka.

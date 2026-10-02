# 0004 - Transactional outbox and Kafka for events

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | enterprise-plan/10 §18; 04 T1, T2 |

## Context
Money-moving side effects (receipts, notifications, reconciliation) must not be lost or duplicated, and dual writes to DB + bus are unsafe.

## Decision
State change and event are written in the same Postgres transaction (outbox); a relay publishes to Apache Kafka (KRaft) with schemas in Apicurio. Consumers are idempotent (`processed_event`) with retry topics and DLQs. Background jobs use a Postgres-backed queue (Procrastinate).

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Celery + broker for everything | Fire-and-forget; no durable workflow state; extra system |
| Redpanda | BSL licence (ADR-0012) |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `enterprise-plan/CHANGES.md`.

## Compliance
Chaos test in the baseline gate: kill the relay mid-flight → no lost or duplicate side effects.

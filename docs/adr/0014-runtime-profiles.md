# 0014 - Runtime profiles: lite inner loop, full outer loop

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.2); team to ratify at kickoff |
| Plan references | docs/enterprise-plan/17 §2.3 to §2.5, §14 |

## Context
The production stack (Kafka, Valkey, Keycloak, OPA, SeaweedFS, Grafana, Kubernetes, OpenTofu) would block daily development and testing if every developer had to run it locally. Enterprise teams separate a fast inner loop from a complete outer loop.

## Decision
Three runtime profiles select drivers through config only: `lite` (default for daily development: PostgreSQL plus in-process drivers), `full` (Compose with the real components, used locally when needed and in the CI integration lane) and `prod` (HUTCH platform). Code patterns (outbox, idempotency, `Money`, `Clock`, token validation, migrations, config resolver, permissions, correlation IDs) exist in every profile. Each port has one parity test suite that every driver must pass. Real drivers are built early in a CI lane (work packages I0 to I3), and deployment artefacts (Helm, OpenTofu) come in hardening.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Full stack on every laptop from day one | Slow setup, heavy machines, blocked developers |
| Mocks only until the end | Big-bang integration risk; light drivers drift from real ones |
| SQLite for local development | Schemas, row-level security and pgvector differ from production |

## Consequences
Daily development needs only Python, Node and PostgreSQL. The composition root is the only place that reads `CLARITY_PROFILE`. CI must run the parity suites against real drivers on a schedule and on PRs labelled `infra`.

## Compliance
Parity suites per port; a review rule rejects `CLARITY_PROFILE` usage outside the composition root (AGENTS.md I20); the I0 to I3 work packages are tracked in the Gantt chart.

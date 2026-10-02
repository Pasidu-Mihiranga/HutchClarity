# 0006 - Runtime profiles: lite and full

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
Running Kafka, Keycloak, OPA, SeaweedFS and Grafana on every laptop blocks the inner loop.

## Decision
`CLARITY_PROFILE=lite|full|prod`. Lite: Postgres + in-process drivers. Full: Compose profile with Kafka, Valkey, SeaweedFS, Keycloak, OPA, OTel/LGTM (Langfuse optional). Prod: HUTCH platform. Only the composition root reads the profile.

## Consequences
Daily dev needs Python, Node and Postgres. Every port has a parity suite both drivers must pass. Business code never branches on profile.

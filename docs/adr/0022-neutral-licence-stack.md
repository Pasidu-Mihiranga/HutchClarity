# 0022 - Neutral, OSI-licensed infrastructure stack

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | enterprise-plan/19 §1–§2; 04 T12, T13 |

## Context
HUTCH legal must approve production use; vendor licence changes (BSL/SSPL) create risk.

## Decision
Runtime components must be OSI-licensed with neutral governance and AWS + Azure managed equivalents: PostgreSQL, Valkey, Apache Kafka (KRaft) + Apicurio, SeaweedFS (S3 API), Keycloak, OPA, OpenBao, OpenTelemetry, OpenFeature/flagd, OpenTofu.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Redis, Redpanda, Confluent registry, HashiCorp Vault, MinIO, Terraform | Non-OSI or source-available licences, or archived community edition |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `enterprise-plan/CHANGES.md`.

## Compliance
Licence scan in CI (SCA); new runtime dependency requires a devlog note with its licence.

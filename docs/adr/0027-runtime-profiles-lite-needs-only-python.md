# 0027 - Runtime profiles: lite needs only Python

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Deciders | Architecture (merged plan v1.3); team to ratify |
| Plan references | enterprise-plan/21 §9; 18 §2.3 |

## Context
Development must never wait for Docker, Kubernetes, Terraform or a database. ADR-0006 kept the prototype infrastructure-free; ADR-0024 made `lite` require PostgreSQL.

## Decision
Three profiles chosen only in the composition root: `lite` (default: in-memory repositories, in-process bus, dev issuers, local key, in-process hutch-sim; needs only Python), `full` (PostgreSQL, Kafka, Keycloak, OPA, Valkey, SeaweedFS, OpenBao, hutch-sim service; via Docker Compose) and `prod` (HUTCH platform). Every port has one parity suite that each driver must pass, and real drivers run in a CI lane from migration step R2.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| PostgreSQL required for lite (ADR-0024) | Blocks first-run and reviewers; parity suites already guarantee the in-memory driver matches |
| Mocks only until the end | Big-bang integration risk |

## Consequences
The migration plan (chapter 21) and `ARCHITECTURE.md` follow this decision. Changing it needs a superseding ADR and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
A test fails if anything outside the composition root reads `CLARITY_PROFILE`; parity suites per port; the nightly CI lane runs the `full` profile.

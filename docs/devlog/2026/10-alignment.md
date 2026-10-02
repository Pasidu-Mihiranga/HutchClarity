# 2026-10 - Alignment with HutchClarity-new baseline

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Authors | Hutch Clarity team |
| Related | ADR-0006 lite/full profiles, Phase I infra parity, Phase F hardening |

## Summary

Brought the main repo toward the HutchClarity-new architecture baseline:

- Docker Compose `lite` / `full` profiles (Postgres always; Kafka, Valkey,
  SeaweedFS, Keycloak, OPA, OTel/LGTM, Langfuse on `full`).
- Integration driver parity kit (mock bus/cache/blob + Kafka / Valkey /
  Seaweed stubs) with contract tests.
- Thin `clarity-worker` and `clarity-stream` entrypoints.
- OPA authz stubs, Alembic-per-module notes, Helm / OpenTofu placeholders.
- CI split (lint, test-legacy, test-new, gitleaks, SBOM placeholder).
- Docs: SECURITY, CONTRIBUTING, CHANGELOG, AGENTS, walkthrough WT-01,
  demo recording guide, architecture mermaid, VERSION `0.2.0-baseline`.

## Follow-ups

- Wire real Kafka/Valkey clients in CI with `CLARITY_FULL=1`.
- Per-module Alembic trees beyond the template.
- Replace SBOM / gitleaks placeholders with production scanners.

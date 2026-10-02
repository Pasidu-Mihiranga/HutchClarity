# 0006 - Deployment contract and infrastructure ports

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | docs/enterprise-plan/18 §2, §3; 04 T14 |

## Context
HUTCH must be able to deploy the prototype on AWS, Azure, a VPS or Kubernetes without rewriting code.

## Decision
Every deployable follows the deployment contract: one OCI image, config via env/files, stateless, health probes, graceful shutdown, separate migration command, JSON logs + OTLP, no secrets in images. Every infrastructure capability (DB, bus, cache, blob, keys, identity, LLM, telemetry) sits behind a port with drivers. The prototype runs on Compose; Helm and OpenTofu reference artefacts are proven in CI on `kind`.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Kubernetes everywhere | Heavy for the prototype |
| Cloud-specific SDKs in domain code | Lock-in |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
Domain code may not import cloud SDKs (import-linter); CI installs the Helm chart on `kind` and runs smoke tests.

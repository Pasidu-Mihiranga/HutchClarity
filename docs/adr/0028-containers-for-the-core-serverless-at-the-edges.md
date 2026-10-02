# 0028 - Containers for the core, serverless at the edges

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Deciders | Architecture (merged plan v1.3); team to ratify |
| Plan references | enterprise-plan/21 §5-6; 04 T17 |

## Context
Telecom operators usually run core business systems on private Kubernetes or OpenShift for data residency and network reach into charging and payment systems. The money path needs strong consistency; other parts are stateless and bursty.

## Decision
The money path (`clarity-api`), stream detectors, integration adapters, signer, workers and AI gateway run as containers. The verify page, receipt rendering, notifications fan-out, channel webhooks, batch analytics and the stateless MCP server may run serverless (Knative/KEDA on HUTCH's platform, or Lambda / Azure Functions in a cloud). Modules start in a modular monolith and are extracted as microservices only on defined triggers (independent scaling, separate team, security zone, release cadence).

## Alternatives considered
| Option | Why not chosen |
|---|---|
| All serverless | Cold starts, short-lived connections and lack of private-network reach conflict with the money path and adapters |
| All microservices from day one | Distributed-monolith cost before value |

## Consequences
The migration plan (chapter 21) and `ARCHITECTURE.md` follow this decision. Changing it needs a superseding ADR and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
Every deployable follows the deployment contract (ADR-0016); extraction of a module requires its parity and acceptance tests to pass against the extracted service before traffic moves.

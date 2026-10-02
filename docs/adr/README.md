# Architecture Decision Records

New ADR: copy [../templates/ADR.md](../templates/ADR.md) to `NNNN-short-title.md`, add a row here in the same PR.

When documents disagree: accepted ADR > [`ARCHITECTURE.md`](../../ARCHITECTURE.md) > plan chapters 17–19 > plan chapters 01–16.

| ADR | Title | Status | Date |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 2026-10-01 |
| [0002](0002-modular-monolith-with-satellites.md) | Modular monolith with separately deployed services | Accepted | 2026-10-01 |
| [0003](0003-schema-per-module.md) | One Postgres schema and DB role per module; no cross-schema joins | Accepted | 2026-10-01 |
| [0004](0004-outbox-and-kafka.md) | Transactional outbox and Kafka for events | Accepted | 2026-10-01 |
| [0005](0005-detectors-zen-tables-opa.md) | Python detectors + ZEN decision tables for rules; OPA for authorization | Accepted | 2026-10-01 |
| [0006](0006-deployment-contract-and-ports.md) | Deployment contract and infrastructure ports | Accepted | 2026-10-01 |
| [0007](0007-identity-keycloak-and-customer-issuer.md) | Identity: Keycloak for staff/admin/machines, Clarity issuer for customers | Accepted | 2026-10-01 |
| [0008](0008-mcp-stateless-resource-server.md) | MCP server: stateless OAuth 2.1 resource server that can only read and propose | Accepted | 2026-10-01 |
| [0009](0009-ai-gateway-model-roles.md) | AI gateway with model roles; Gemini + Groq free tiers for the prototype | Accepted | 2026-10-01 |
| [0010](0010-template-only-notifications.md) | Customer notifications use approved templates only | Accepted | 2026-10-01 |
| [0011](0011-policy-change-lifecycle.md) | One lifecycle for every policy change | Accepted | 2026-10-01 |
| [0012](0012-neutral-licence-stack.md) | Neutral, OSI-licensed infrastructure stack | Accepted | 2026-10-01 |
| [0013](0013-living-documentation.md) | Living documentation system | Accepted | 2026-10-01 |
| [0014](0014-runtime-profiles.md) | Runtime profiles: lite inner loop, full outer loop | Accepted | 2026-10-01 |

## Legacy (prototype era)

Earlier prototype ADRs and short alignment stubs superseded by the table above are kept under [`legacy/`](legacy/) for history. Do not cite them for new work.

# Architecture Decision Records

Decisions that shaped this system, with the alternatives considered and what
each one costs. A decision that is not written down gets re-argued, or quietly
reversed.

| # | Decision | Status |
|---|---|---|
| [0001](0001-yaml-rule-packs-over-python-detectors.md) | Cause rules are YAML rule packs, not Python plugins | Accepted |
| [0002](0002-policy-as-scoped-effective-dated-data.md) | Policy is scoped, effective-dated data with guardrails | Accepted |
| [0003](0003-policy-change-governance.md) | Every policy change has a class, an impact report and two sets of eyes | Accepted |
| [0004](0004-mcp-holds-no-execute-capability.md) | The MCP server holds no capability to execute | Accepted |
| [0005](0005-idempotency-claimed-before-side-effects.md) | An idempotency key is claimed before anything is consumed | Accepted |
| [0006](0006-prototype-runs-with-no-infrastructure.md) | The prototype runs with no infrastructure, behind swappable ports | Accepted |
| [0007](0007-confirmation-tokens-never-leave-the-server.md) | Confirmation tokens are minted and spent server-side | Accepted |
| [0008](0008-risk-signals-derived-from-evidence.md) | Risk signals are derived from evidence, not supplied by callers | Accepted |
| [0009](0009-no-model-configured-by-default.md) | No language model is configured by default | Accepted |
| [0010](0010-identity-is-issued-here-but-federated-later.md) | Clarity issues its own tokens now, behind the interface Keycloak will fill | Accepted |
| [0011](0011-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0012](0012-modular-monolith-with-satellites.md) | Modular monolith with separately deployed services | Accepted |
| [0013](0013-schema-per-module.md) | One Postgres schema and DB role per module; no cross-schema joins | Accepted |
| [0014](0014-outbox-and-kafka.md) | Transactional outbox and Kafka for events | Accepted |
| [0015](0015-detectors-zen-tables-opa.md) | Python detectors + ZEN decision tables for rules; OPA for authorization | Superseded by 0026 |
| [0016](0016-deployment-contract-and-ports.md) | Deployment contract and infrastructure ports | Accepted |
| [0017](0017-identity-keycloak-and-customer-issuer.md) | Identity: Keycloak for staff/admin/machines, Clarity issuer for customers | Accepted |
| [0018](0018-mcp-stateless-resource-server.md) | MCP server: stateless OAuth 2.1 resource server that can only read and propose | Accepted |
| [0019](0019-ai-gateway-model-roles.md) | AI gateway with model roles; Gemini + Groq free tiers for the prototype | Accepted |
| [0020](0020-template-only-notifications.md) | Customer notifications use approved templates only | Accepted |
| [0021](0021-policy-change-lifecycle.md) | One lifecycle for every policy change | Accepted |
| [0022](0022-neutral-licence-stack.md) | Neutral, OSI-licensed infrastructure stack | Accepted |
| [0023](0023-living-documentation.md) | Living documentation system | Accepted |
| [0024](0024-runtime-profiles.md) | Runtime profiles: lite inner loop, full outer loop | Superseded by 0027 |
| [0025](0025-migrate-structure-keep-logic.md) | Migrate the prototype: rewrite structure, replace infrastructure, keep proven logic | Accepted |
| [0026](0026-rules-yaml-packs-zen-outcomes-opa-authz.md) | Rules: YAML cause packs, ZEN outcome tables, OPA for authorization | Accepted |
| [0027](0027-runtime-profiles-lite-needs-only-python.md) | Runtime profiles: lite needs only Python | Accepted |
| [0028](0028-containers-for-the-core-serverless-at-the-edges.md) | Containers for the core, serverless at the edges | Accepted |
| [0029](0029-module-interaction-calls-and-events.md) | Module interaction: public calls for answers, outbox events for side effects | Accepted |
| [0030](0030-bounded-agency-flows-and-grounded-rag.md) | Bounded agency: flows as state machines, tools by allowlist, grounded RAG | Accepted |
| [0031](0031-next-js-14-until-16-passes-the-browser-suite.md) | Next.js 14 until 16 passes the browser suite | Accepted |
| [0033](0033-audit-record-hash-covers-the-whole-record.md) | The audit record hash covers the whole record | Accepted |
| [0034](0034-one-persisted-audit-trail.md) | One persisted audit trail for every process | Accepted |
| [0035](0035-signed-audit-checkpoints-with-a-separate-key.md) | Signed audit checkpoints with a separate key, and a public witness | Accepted |
| [0036](0036-audit-access-as-grants-under-separation-of-duties.md) | Audit access as time-boxed grants under separation of duties | Accepted |
| [0037](0037-assurance-is-a-leaf-module-that-reacts-to-the-trail.md) | Assurance is a leaf module that reacts to the trail | Accepted |
| [0038](0038-audit-recovery-measured-against-an-external-checkpoint.md) | Audit recovery is measured against an external checkpoint | Accepted |
| [0039](0039-audit-lifecycle-archive-hold-and-crypto-shred.md) | The audit trail is archived, held and crypto-shredded, never deleted | Accepted |
| [0040](0040-conversation-transcripts-are-records-not-memory.md) | Conversation transcripts are records, not memory | Accepted |
| [0041](0041-a-session-has-an-absolute-deadline.md) | A session has an absolute deadline | Accepted |
| [0042](0042-the-issuer-signs-from-a-key-ring.md) | The issuer signs from a key ring | Accepted |
| [0043](0043-a-persona-propensity-never-sets-a-reported-band.md) | A persona propensity never sets a reported band | Accepted |
| [0044](0044-the-calibration-gate-opens-on-evidence-nobody-here-can-write.md) | The calibration gate opens on evidence nobody here can write | Accepted |
ADRs 0001-0010 were written while building the prototype; 0011-0024 come from the v1.2 plan line; 0025-0028 belong to the merged plan v1.3. Templates: [../templates/ADR.md](../templates/ADR.md).

## Writing one

Status: `Proposed` -> `Accepted` / `Rejected` -> `Superseded by NNNN`. Never
delete an ADR; supersede it. Each one states context, the decision, the
alternatives and why they lost, the consequences, and how compliance is
checked.

The enterprise plan in [`../enterprise-plan/`](../enterprise-plan/README.md) is
the intended design. These records say what was actually decided while
building, and why it sometimes differs.

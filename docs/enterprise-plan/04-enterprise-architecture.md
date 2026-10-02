# Hutch Clarity - Enterprise System Architecture

[← 03-requirements-personas-journeys.md](03-requirements-personas-journeys.md) · [← Plan index](README.md) · [05-architecture-diagrams.md →](05-architecture-diagrams.md)

> Part of the **Hutch Clarity Enterprise Project Plan**. Labels: `[DECK Sx]` = stated in deck slide x · `[PROPOSED]` = expanded by this plan · **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION** / **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**. See the [index](README.md) for the full legend.

> **Plan v1.1 (2026-10-01).** Updated to match [17](17-build-blueprint.md), [18](18-tech-stack-and-ai.md) and [19](19-policy-change-management.md). Change record: [CHANGES.md](CHANGES.md).

## 7. Enterprise System Architecture

The baseline is the deck's architecture `[DECK S12]`. Its logical flow is preserved: **Channels → Orchestration → Clarity Core → AI Services → Tool Layer → Integration Adapters → HUTCH Systems → Data Platform**.

Deck colour semantics are kept in every diagram:
- **Orange:** deterministic rules that move money.
- **Grey:** AI for language, patterns and prediction.
- **Deep orange:** proof for the customer.

### 7.1 Layer responsibilities

| Layer | Components | Responsibility | Deck / Proposed |
|---|---|---|---|
| **Channels** | Web (hutch.lk), Hutch app WebView, WhatsApp (text + voice), SMS/USSD, Clarity Desk, Ops console | Customer and staff touchpoints; one Next.js/TS PWA codebase for web, app module and consoles | `[DECK S12, S13]` |
| **Edge** | CDN, WAF, API gateway, bot protection, rate limiting, token validation | Block floods and bots, enforce quotas per MSISDN token / IP / staff user, terminate TLS | WAF + rate limits `[DECK S8]`; gateway `[PROPOSED]` |
| **Orchestration** | Identity broker (OTP, SSO), language detection, session and conversation state, message batching, router, handoff checker | Route each turn to disputes, policy answers or self-service flows; handoff check every turn | `[DECK S12]` |
| **Clarity Core** (deterministic) | Case Service, Timeline Builder, Cause Detectors (rule engine), Decision Policy (OPA), Tool Layer, Trust Receipt Service, Reconciliation | Evidence → cause → decision → action → proof; versioned and audited | `[DECK S12]`; reconciliation `[DECK S7]` |
| **AI Services** | AI gateway (model router, masking enforcement, quota), Language LLMs (extract, explain, verify), RAG retriever, STT/TTS, Autopsy, Foresight, semantic cache | Language, retrieval, patterns and prediction. **No authority over money.** | `[DECK S12–S14]` |
| **MCP** | Hutch Clarity MCP server (+ policy, audit) | The only path by which an LLM/agent can read case data or *propose* actions | `[DECK S13]` "MCP tools"; design `[PROPOSED]` |
| **Integration adapters** | Payments, Charging, Catalogue, VAS consent, Usage/FUP, Tickets/CRM; + Identity/OTP, Notifications, Risk signals `[PROPOSED]` | TM Forum-shaped canonical contracts. Read into the timeline; write **only** via the tool layer. | `[DECK S12]` |
| **HUTCH systems** | OCS/charging, payment gateway, product catalogue, DCB/VAS platform, CDR/PCRF, CRM/ticketing, SMSC/USSD gateway, IAM | System of record. **All REQUIRE HUTCH CONFIRMATION.** | Categories `[DECK S12]` |
| **Data platform** | PostgreSQL 18 (schema per module; cases, ledger, pgvector), Valkey (Redis protocol: sessions, exact answer cache, idempotency fast path), Apache Kafka 4 + Apicurio registry (live events, early warning), analytics warehouse (Snowflake or HUTCH standard), S3-API object storage (WORM) | Operational state, cache, events, analytics, artefacts | `[DECK S12]`; object storage `[PROPOSED]` |
| **Operations** | OpenTelemetry, Grafana (+ Prometheus/Loki/Tempo or HUTCH equivalents), Langfuse (self-hosted), SIEM, audit ledger | Trace every call, LLM observability, security monitoring | `[DECK S8, S12]` |

How these logical layers are deployed (a modular monolith plus separately deployed services), the layer import rules and the module catalogue are defined in [17 §2–§4](17-build-blueprint.md).

### 7.2 Technology change analysis
The deck stack is retained. Where this plan **refines or adds**, the reasoning follows the required format.

| # | Current proposal | Limitation | Proposed alternative | Why better |
|---|---|---|---|---|
| T1 | Celery for async work `[DECK S13]` | Celery tasks are fire-and-forget and need a separate broker. Human-in-the-loop approvals lasting hours or days, compensations and exactly-once side effects need durable state. | Case and approval lifecycles as a **PostgreSQL state machine + transactional outbox → Kafka**. Background jobs on a **Postgres-backed job queue** (Procrastinate) behind a `JobQueue` port; Celery stays possible as a driver. | Durable, queryable, auditable state with one fewer system to run. Temporal only if HUTCH already runs it. |
| T2 | Kafka for live events `[DECK S12]` | No schema governance stated; uncontrolled event evolution breaks consumers. | Kafka + **Schema Registry** (Apicurio, Confluent-compatible API; Avro or Protobuf, BACKWARD compatibility) + DLQ topics. | Safe versioning and replay; required for the financial event trail. |
| T3 | "Versioned rule packs · OPA · stream detectors" `[DECK S13]` | Rego is excellent for authorization but awkward for temporal evidence logic (e.g., "two captures within 10 min with one credit"), and a custom YAML DSL is costly to build and still not business-editable. | **Split three ways:** cause detectors = versioned **Python detector plugins** (`rule_id@version`) with a manifest and parameters in versioned config; outcome matrix, caps and thresholds = **GoRules ZEN decision tables** (JDM, business-editable); authorization and MCP access = **OPA/Rego**. | Each tool where it is strongest. All three are versioned, signed, tested and replayable ([09](09-rules-decision-receipts.md), [19](19-policy-change-management.md)). |
| T4 | PostgreSQL ledger + "hash-chained audit" `[DECK S8, S12]` | A hash chain inside the same DB can be rewritten by a privileged DB admin. | Keep the PG hash chain, and **anchor** a chain-head hash every N minutes to **WORM object storage** (object-lock) and the SIEM. | Tamper evidence that holds even against privileged insiders. |
| T5 | Snowflake for analytics and Foresight seeds `[DECK S12]` | S2 suggests HUTCH uses Snowflake, but this is unconfirmed. Mandating it could duplicate the HUTCH data estate. | **Use HUTCH's existing warehouse** (Snowflake if confirmed) through an analytics interface. **REQUIRES HUTCH CONFIRMATION.** | No duplicate platform. Data governance stays with HUTCH. |
| T6 | "Reasoning + non-reasoning LLMs; model IDs in config" `[DECK S13]` | Direct provider calls scatter masking, quotas and fallback logic across services. | **AI gateway service** with logical model **roles** (`fast-text`, `extract`, `reason`, `judge`, `guard`, `embed`, `stt`, `tts`) mapped to providers in config. Prototype: Gemini + Groq free tiers on synthetic, masked data. Production: HUTCH's choice (Vertex AI, Azure, Bedrock or self-hosted vLLM) by config ([18 §4](18-tech-stack-and-ai.md)). | One enforcement point for masking, cost, quotas, routing and failover. Changing provider needs no code change. |
| T7 | Redis answer cache (RedisVL) `[DECK S14]` | Semantic matching can return a wrong but similar answer. RedisVL needs the Redis query engine, which Valkey does not guarantee. | Keep the cache tiers. **Exact match in Valkey; meaning match on pgvector**, only for generic, CX-approved, catalogue-keyed answers `[DECK S14]`, with a similarity threshold, the catalogue version in the key and a TTL. Case-specific answers are never cached. | Preserves 0-token answers on neutral components without leaking or misapplying content. |
| T8 | MiroFish engine (OASIS · GraphRAG · Zep) `[DECK S13]` | Research-grade components; licensing and operational maturity unknown; Zep may have commercial terms. | Isolate as a **sandboxed Foresight service** on aggregates only, behind a stable interface. Add a statistical baseline. Licence review is a Phase 2 gate. | Contains risk; Foresight can't affect customer-facing paths. |
| T9 | Playwright receipt rendering `[DECK S13]` | Headless browsers are heavy and an attack surface. | Keep (correct Sinhala/Tamil shaping), run in an **isolated render pool** with no network egress and a template-only input. | Correct output and contained risk. |
| T10 | Ed25519 signing `[DECK S6]` | Key custody is unspecified. | **Signing service** with keys in an HSM or a KMS that supports Ed25519; otherwise an envelope-encrypted key loaded only into the signing pod. `kid` rotation and public key published at `/.well-known/clarity-keys`. | Verifiable, rotatable and auditable signatures. |
| T11 | ~13 microservices from day one (v1.0 §43) | Distributed-monolith overhead: many deployables, network hops and versioning before any business value | **Modular monolith** with a schema and DB role per module, plus separately deployed services where trust, keys or scaling differ (MCP, signer, AI gateway, channel gateway, workers, `hutch-sim`) ([17 §4](17-build-blueprint.md)) | Same boundaries; any module can be extracted later without a rewrite |
| T12 | Redis `[DECK S12]` | Redis moved to a tri-licence including AGPL/SSPL | **Valkey** (Linux Foundation, BSD-3), Redis-protocol compatible | Neutral licence; managed on AWS and Azure |
| T13 | Source-available or archived infrastructure (Redpanda dev broker, HashiCorp Vault, Confluent registry, MinIO, Terraform) | BSL / non-OSI licences or archived community edition | **Apache Kafka (KRaft), OpenBao, Apicurio, SeaweedFS, OpenTofu** | Passes the OSI-licence criterion ([18 §1](18-tech-stack-and-ai.md)) |
| T14 | Kubernetes as the baseline for every environment | Heavy for a prototype; ties the team to one platform | **Deployment contract** (OCI images, env config, health probes, stateless processes, migration job, OTLP). Runtime profiles (ADR-0014): `lite` (PostgreSQL only) for daily development, `full` Compose profile and the CI lane for real drivers; Helm + OpenTofu reference artefacts proven in CI on `kind` during hardening | HUTCH can deploy to AWS, Azure, a VPS or Kubernetes without code change |
| T15 | Self-hosted LLM as the primary tier | No GPUs during the prototype | Role-based routing with Gemini + Groq free tiers for the prototype (synthetic data only); HUTCH's models later by config | Zero AI cost in the prototype; no lock-in |
| T16 | Only rules have a change process | Parameters, decision tables, templates, knowledge and catalogue mappings also change, often | **One policy artefact lifecycle** for every kind of change ([19](19-policy-change-management.md)) | Telecom policy change is routine, safe and auditable |

Rows T11–T16 were added in plan v1.1. No other deck technologies are replaced.
---

[← 03-requirements-personas-journeys.md](03-requirements-personas-journeys.md) · [← Plan index](README.md) · [05-architecture-diagrams.md →](05-architecture-diagrams.md)

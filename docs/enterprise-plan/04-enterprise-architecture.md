# Hutch Clarity — Enterprise System Architecture

[← 03-requirements-personas-journeys.md](03-requirements-personas-journeys.md) · [← Plan index](README.md) · [05-architecture-diagrams.md →](05-architecture-diagrams.md)

> Part of the **Hutch Clarity Enterprise Project Plan**. Labels: `[DECK Sx]` = stated in deck slide x · `[PROPOSED]` = expanded by this plan · **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION** / **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**. See the [index](README.md) for the full legend.

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
| **Data platform** | PostgreSQL 16 (cases, ledger, pgvector), Redis (sessions, answer cache, idempotency), Kafka (live events, early warning), analytics warehouse (Snowflake or HUTCH standard), object storage (WORM) | Operational state, cache, events, analytics, artefacts | `[DECK S12]`; object storage `[PROPOSED]` |
| **Operations** | OpenTelemetry, Grafana (+ Prometheus/Loki/Tempo or HUTCH equivalents), Langfuse (self-hosted), SIEM, audit ledger | Trace every call, LLM observability, security monitoring | `[DECK S8, S12]` |

### 7.2 Technology change analysis
The deck stack is retained. Where this plan **refines or adds**, the reasoning follows the required format.

| # | Current proposal | Limitation | Proposed alternative | Why better |
|---|---|---|---|---|
| T1 | Celery for async work `[DECK S13]` | Celery tasks are fire-and-forget. Human-in-the-loop approvals lasting hours or days, compensations and exactly-once side effects need durable state that a broker queue doesn't provide. | **Keep Celery** for stateless batch jobs (receipt rendering, Autopsy batches, notifications). Model case and approval lifecycles as a **PostgreSQL state machine + transactional outbox → Kafka**. | Workflow state survives restarts, is queryable and auditable, and avoids adding a workflow engine. Temporal is optional only if HUTCH already runs it. |
| T2 | Kafka for live events `[DECK S12]` | No schema governance stated; uncontrolled event evolution breaks consumers. | Kafka + **Schema Registry** (Avro or Protobuf, BACKWARD compatibility) + DLQ topics. | Safe versioning and replay; required for the financial event trail. |
| T3 | "Versioned rule packs · OPA · stream detectors" `[DECK S13]` | Rego is excellent for policy and authorization, but awkward for temporal evidence logic (e.g., "two captures within 10 min with one credit"). | **Split:** cause detectors = versioned declarative rule packs (YAML) evaluated by a Python engine with typed predicates over the timeline. Decision policy, caps and MCP authorization = **OPA/Rego**. | Each tool is used where it is strongest. Both are versioned, tested and replayable. |
| T4 | PostgreSQL ledger + "hash-chained audit" `[DECK S8, S12]` | A hash chain inside the same DB can be rewritten by a privileged DB admin. | Keep the PG hash chain, and **anchor** a chain-head hash every N minutes to **WORM object storage** (object-lock) and the SIEM. | Tamper evidence that holds even against privileged insiders. |
| T5 | Snowflake for analytics and Foresight seeds `[DECK S12]` | S2 suggests HUTCH uses Snowflake, but this is unconfirmed. Mandating it could duplicate the HUTCH data estate. | **Use HUTCH's existing warehouse** (Snowflake if confirmed) through an analytics interface. **REQUIRES HUTCH CONFIRMATION.** | No duplicate platform. Data governance stays with HUTCH. |
| T6 | "Reasoning + non-reasoning LLMs; model IDs in config" `[DECK S13]` | Direct provider calls scatter masking, quotas and fallback logic across services. | **AI gateway service.** Primary tier is a self-hosted open-weight model (vLLM-served inside HUTCH); a hosted API tier, masked text only, is fallback/escalation. | One enforcement point for masking, cost, routing and failover. Data residency is preserved. |
| T7 | Redis answer cache (RedisVL) `[DECK S14]` | Semantic matching can return a wrong but similar answer. | Keep. Semantic cache **only for generic, CX-approved, catalogue-keyed answers** `[DECK S14]`, with a similarity threshold, a catalogue version in the key and TTL. Case-specific answers are never cached. | Preserves 0-token answers without leaking or misapplying content. |
| T8 | MiroFish engine (OASIS · GraphRAG · Zep) `[DECK S13]` | Research-grade components; licensing and operational maturity unknown; Zep may have commercial terms. | Isolate as a **sandboxed Foresight service** on aggregates only, behind a stable interface. Add a statistical baseline. Licence review is a Phase 2 gate. | Contains risk; Foresight can't affect customer-facing paths. |
| T9 | Playwright receipt rendering `[DECK S13]` | Headless browsers are heavy and an attack surface. | Keep (correct Sinhala/Tamil shaping), run in an **isolated render pool** with no network egress and a template-only input. | Correct output and contained risk. |
| T10 | Ed25519 signing `[DECK S6]` | Key custody is unspecified. | **Signing service** with keys in an HSM or a KMS that supports Ed25519; otherwise an envelope-encrypted key loaded only into the signing pod. `kid` rotation and public key published at `/.well-known/clarity-keys`. | Verifiable, rotatable and auditable signatures. |

No other deck technologies are replaced.
---

[← 03-requirements-personas-journeys.md](03-requirements-personas-journeys.md) · [← Plan index](README.md) · [05-architecture-diagrams.md →](05-architecture-diagrams.md)

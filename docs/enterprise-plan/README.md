# Hutch Clarity - Enterprise Project Plan

This folder turns the 17-slide *Hutch Clarity* deck into an enterprise-grade technical and implementation plan, from hackathon prototype to HUTCH production. The plan follows the HUTCH Hackathon Final Submission Guidelines. Source documents are in [`documents/`](../../documents/). Chapters 01–17 use global section numbers (§1–§52); chapters 18–21 use local numbers (cited as "18 §2.3"). Where they disagree, 18–21 win (see [CHANGES.md](CHANGES.md)).

**Explain every rupee. Fix it by rule. Prove it won't happen again.** `[DECK S1]`

| Item | Value |
|---|---|
| Document | Enterprise Project Plan - Hackathon Prototype → HUTCH Production |
| Version / date | **v1.12** · 2026-10-04 (see [CHANGES.md](CHANGES.md)) |
| Sources | (1) *Hutch Clarity* 17-slide deck - authoritative concept; (2) *HUTCH Hackathon Final Submission Guidelines* |
| Not available | SRS, architecture, API, DB, UML, infra, MCP, test, project, risk, RACI and cost documents. **All of these are created in this plan.** |
| Planning start | **2027-01-04 - Assumed project start date for planning purposes.** |
| LLM stance | Provider-neutral AI gateway with logical model **roles**. Default: no model (CX-approved templates, 0 tokens, ADR-0009). Opt-in prototype: Gemini + Groq free tiers on synthetic, masked data only. Production: HUTCH's provider or self-hosted models, by config ([19 §4](19-tech-stack-and-ai.md)). |

### Labelling legend (used everywhere)

| Label | Meaning |
|---|---|
| `[DECK Sx]` | Stated explicitly on slide *x* of the Hutch Clarity deck |
| `[PROPOSED]` | Enterprise design expanded by this plan (inferred, not in the deck) |
| **ASSUMPTION** | Planning assumption; replace with real data when available |
| **REQUIRES HUTCH CONFIRMATION** | Depends on a HUTCH system, policy, contract or decision we cannot know |
| **PROPOSED TARGET – REQUIRES HUTCH VALIDATION** | Numeric NFR/KPI target proposed by the team |
| *Illustrative* | Sample values shown for explanation only, never measured HUTCH results |

> **Integrity statement.** No HUTCH APIs, credentials, environments or production data were provided (Guidelines §4), and none are assumed to exist. Every HUTCH system named here is a *category* inferred from the deck's adapter list `[DECK S12]`. Its real interface, owner and protocol are **REQUIRES HUTCH CONFIRMATION**. Customer quotes in the deck are paraphrased public posts: "patterns, not statistics" `[DECK S2]`. The Hostinger resolution figures are Hostinger-reported `[DECK S3]`.

## Document map

| File | Contents | Sections |
|---|---|---|
| [01-executive-summary-problem.md](01-executive-summary-problem.md) | Executive Summary & Problem Analysis | §1, §2 |
| [02-solution-capabilities.md](02-solution-capabilities.md) | Solution Capabilities | §3 |
| [03-requirements-personas-journeys.md](03-requirements-personas-journeys.md) | Requirements, Personas & Customer Journeys | §4, §5, §6 |
| [04-enterprise-architecture.md](04-enterprise-architecture.md) | Enterprise System Architecture | §7 |
| [05-architecture-diagrams.md](05-architecture-diagrams.md) | Architecture Diagrams | §8 |
| [06-integration-tmf.md](06-integration-tmf.md) | HUTCH Integration Strategy & TM Forum | §9 |
| [07-mcp.md](07-mcp.md) | MCP Architecture & Tool Catalogue | §10, §11 |
| [08-ai-architecture.md](08-ai-architecture.md) | AI Architecture, RAG, Guardrails & Evaluation | §12 |
| [09-rules-decision-receipts.md](09-rules-decision-receipts.md) | Rule Engine, Decision Policy & Trust Receipts | §13, §14, §15 |
| [10-data-api-events.md](10-data-api-events.md) | Data, API & Event Architecture | §16, §17, §18 |
| [11-security-privacy-audit.md](11-security-privacy-audit.md) | Security, Privacy & Audit | §19, §20 |
| [12-platform-devops-testing-observability.md](12-platform-devops-testing-observability.md) | Technology Stack, Deployment, DevOps, Testing & Observability | §21, §22, §23, §24, §25 |
| [13-delivery-plan.md](13-delivery-plan.md) | Delivery Plan: Phases, WBS, Gantt, Critical Path, Team, RACI, Dependencies | §26, §27, §28, §29, §30, §31, §32 |
| [14-risk-pilot-readiness-operations.md](14-risk-pilot-readiness-operations.md) | Risks, Pilot, Production Readiness & Operations | §33, §34, §35, §36 |
| [15-cost-scale-failure-kpi.md](15-cost-scale-failure-kpi.md) | AI Cost, Scalability, Failure Handling & KPIs | §37, §38, §39, §40 |
| [16-gap-submission-repo-docs.md](16-gap-submission-repo-docs.md) | Prototype Gap, Hackathon Mapping, Repository, Documentation & Recommendations | §41, §42, §43, §44, §45 |
| [17-governance-compliance-change-cost.md](17-governance-compliance-change-cost.md) | Governance & Stage Gates, Release Plan & Traceability, Compliance, Change Management, Effort & TCO, Assumptions Register, Post-Production Support | §46, §47, §48, §49, §50, §51, §52 |
| [18-build-blueprint.md](18-build-blueprint.md) | Build Blueprint: baseline, modules, layers, runtime profiles, identity, UI, data flow, notifications, MCP, dependency graph | ch. 18 (local § numbers) |
| [19-tech-stack-and-ai.md](19-tech-stack-and-ai.md) | Enterprise tech stack with selection criteria, AWS/Azure/on-prem mapping, AI model roles (Gemini + Groq) | ch. 19 |
| [20-policy-change-management.md](20-policy-change-management.md) | Policy & change management: packs, prices, caps, regulations, rules, wording | ch. 20 |
| [21-migration-and-deployment-plan.md](21-migration-and-deployment-plan.md) | **Migration plan** (prototype → target architecture) and **runtime model**: containers for the core, serverless at the edges, microservice extraction path | ch. 21 |
| [22-agentic-assistant-and-rag.md](22-agentic-assistant-and-rag.md) | **Agentic assistant**: flows as state machines, bounded agent step, RAG with citations, guardrails, evaluation | ch. 22 |
| [CHANGES.md](CHANGES.md) | Plan change record and the process for changing this plan | - |

## Reading paths

| Audience | Start with |
|---|---|
| Hackathon judges | [01](01-executive-summary-problem.md) → [05](05-architecture-diagrams.md) → [06](06-integration-tmf.md) → [13](13-delivery-plan.md) → [15](15-cost-scale-failure-kpi.md) → [16](16-gap-submission-repo-docs.md) → [17](17-governance-compliance-change-cost.md) |
| Solution architects / engineering | [21](21-migration-and-deployment-plan.md), [18](18-build-blueprint.md), [19](19-tech-stack-and-ai.md), [20](20-policy-change-management.md), [04](04-enterprise-architecture.md), [05](05-architecture-diagrams.md), [09](09-rules-decision-receipts.md), [10](10-data-api-events.md), [12](12-platform-devops-testing-observability.md) |
| AI / MCP teams | [22](22-agentic-assistant-and-rag.md), [07](07-mcp.md), [08](08-ai-architecture.md), [15](15-cost-scale-failure-kpi.md) |
| Security & compliance | [11](11-security-privacy-audit.md), [17 §48](17-governance-compliance-change-cost.md), [07](07-mcp.md), [14](14-risk-pilot-readiness-operations.md) |
| CX, product, finance, business | [01](01-executive-summary-problem.md), [02](02-solution-capabilities.md), [03](03-requirements-personas-journeys.md), [09](09-rules-decision-receipts.md), [14](14-risk-pilot-readiness-operations.md), [17](17-governance-compliance-change-cost.md) |
| Project management / DevOps / SRE | [13](13-delivery-plan.md), [17](17-governance-compliance-change-cost.md), [12](12-platform-devops-testing-observability.md), [14](14-risk-pilot-readiness-operations.md) |

## Diagrams
All diagrams are written in Mermaid, which GitHub, GitLab and most Markdown viewers render. The full index of all 39 diagrams is in [05-architecture-diagrams.md § 8.1](05-architecture-diagrams.md#81-diagram-index-all-39-architecture-diagrams-in-this-plan).

## Revision history

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-10-01 | First complete plan: 45 sections, 34 diagrams, built from the deck and the submission guidelines |
| v1.1 | 2026-10-01 | **Plan audit.** The plan was checked against the 51-point brief, the Final Submission Guidelines and all 17 deck slides. Gaps found and added are listed below. |
| v1.2 | 2026-10-01 | Parallel line ("Plan v1"): build blueprint, tech stack with AI roles, policy change management, runtime profiles. Kept as chapters 18–20. |
| v1.3 | 2026-10-02 | **Merged plan.** v1.1 audit + the v1.2 line + chapter 21 (migration and runtime model). Details in [CHANGES.md](CHANGES.md). |
| v1.4 | 2026-10-02 | Module interaction model (21 §11, ADR-0029); R0 acceptance suite; D7. |
| v1.5 | 2026-10-02 | Agentic assistant and RAG (ch. 22, ADR-0030); per-module backlog with acceptance tests and DoD (`docs/backlog`). |
| v1.6 | 2026-10-02 | Drivers built so far: persistence and event bus ports with their parity suites and the Kafka driver (19 §2.3.1, B02 and B03). |
| v1.7 | 2026-10-02 | Wave 1 core migration: policy-backed rule parameters, active rule catalogue status and the corrected module interaction map. |
| v1.8 | 2026-10-02 | R4 started: H01 extracted the simulated HUTCH estate behind parity-tested HTTP drivers. |
| v1.9 | 2026-10-02 | R6 started: N01 added event-driven, template-only notification routing and delivery tracking. |
| v1.10 | 2026-10-02 | R6 continued: P01 added policy-backed stream detectors and zero-contact duplicate-reload resolution. |
| v1.11 | 2026-10-04 | R5: the static UI is retired and the Next.js apps are the only UI; Next.js 14 is the current framework (FE01, ADR-0031). |
| v1.12 | 2026-10-04 | Chapter 22 section 9 restated: no conversation content steers a later turn, and a bounded transcript is kept as a record (ADR-0040). |

### v1.1 audit: gaps found and added

| # | Gap found | Basis | Added in |
|---|---|---|---|
| 1 | Prototype scope was implicit | Brief §1 "prototype scope" | [§1.9](01-executive-summary-problem.md) |
| 2 | Proactive care had no consent, quiet-hours or frequency controls | Deck S5–S6 | [§3.6](02-solution-capabilities.md) + Diagram 38 |
| 3 | Personalization and family guardian not designed | Deck S5–S6 | [§3.7](02-solution-capabilities.md) |
| 4 | "Flow DSL" named but not designed | Deck S11, S15 | [§3.8](02-solution-capabilities.md) |
| 5 | FRs missing: TTS reply, shop channel, receipt lookup by ID, kill switches, proactive pacing | Deck S5, S6 | [§4.1](03-requirements-personas-journeys.md) FR-COP-15, FR-CH-05, FR-TR-07, FR-GOV-04/05 |
| 6 | NFRs missing: low-bandwidth/older devices, data residency, AI cost budget | Deck S15; S8 | [§4.2](03-requirements-personas-journeys.md) NFR-PERF-06, NFR-PRV-03, NFR-COST-01 |
| 7 | Personas missing: shop staff, external verifier (TRCSL/auditor) | Deck S5, S6, S9 | [§5](03-requirements-personas-journeys.md) |
| 8 | No Before → During → After journey summary | Guidelines §8; Deck S16 | [§6.7](03-requirements-personas-journeys.md) |
| 9 | Channel limits (WhatsApp 24-h window/templates, SMS UCS-2, USSD) not addressed | Channel specs | [§9.7](06-integration-tmf.md) |
| 10 | Forecast/risk-model disclosure only for bill-shock | Guidelines §6.3 | [§12.9](08-ai-architecture.md) |
| 11 | Reconciliation and financial controls named but not designed | Deck S7, S14 | [§14.4](09-rules-decision-receipts.md) + Diagram 37 |
| 12 | No data governance / data quality design | Enterprise practice | [§16.3](10-data-api-events.md) |
| 13 | No test data management | Enterprise practice | [§24.1](12-platform-devops-testing-observability.md) |
| 14 | No SLOs / error budgets | Enterprise practice | [§25.4](12-platform-devops-testing-observability.md) |
| 15 | No benefits measurement method (baseline, control, attribution) | Guidelines §6.5 | [§40.1](15-cost-scale-failure-kpi.md) |
| 16 | AI/LLM disclosure not consolidated into the required template | Guidelines §6.1 | [§42.3](16-gap-submission-repo-docs.md) |
| 17 | Deck not mapped to the 10 recommended slides; no demo storyboard; no demo-readiness checklist | Guidelines §9–§11 | [§42.4–42.6](16-gap-submission-repo-docs.md) |
| 18 | No project governance or stage gates | Enterprise practice | [§46](17-governance-compliance-change-cost.md) + Diagram 35 |
| 19 | No release plan or requirements traceability | Enterprise practice | [§47](17-governance-compliance-change-cost.md) + Diagram 36 |
| 20 | No regulatory/compliance mapping (Gazette, TRCSL, PDPA, PCI scope) | Deck S3, S8 | [§48](17-governance-compliance-change-cost.md) |
| 21 | No change management, training or communications plan | Enterprise practice | [§49](17-governance-compliance-change-cost.md) |
| 22 | Cost model covered AI only (no delivery effort or TCO) | Brief: "Cost model" missing | [§50](17-governance-compliance-change-cost.md) |
| 23 | No assumptions register or data-provenance classification | Guidelines §6.4 | [§51](17-governance-compliance-change-cost.md) |
| 24 | Post-production support, hypercare, warranty, knowledge transfer not defined | Guidelines §5.1 | [§52](17-governance-compliance-change-cost.md) + Diagram 39 |
| 25 | README tagline duplicated; diagrams not render-checked | Housekeeping | Fixed; all Mermaid blocks render-validated |

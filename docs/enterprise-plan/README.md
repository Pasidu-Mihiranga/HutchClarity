# Hutch Clarity - Enterprise Project Plan

**Explain every rupee. Fix it by rule. Prove it won't happen again.**

This folder turns the 17-slide *Hutch Clarity* deck into an enterprise-grade technical and implementation plan, from hackathon prototype to HUTCH production. The plan follows the HUTCH Hackathon Final Submission Guidelines. The source documents (deck PDF and guidelines DOCX) are in the repository root. **Changes to this plan follow the process in [CHANGES.md](CHANGES.md).**

**Explain every rupee. Fix it by rule. Prove it won't happen again.** `[DECK S1]`

| Item | Value |
|---|---|
| Document | Enterprise Project Plan - Hackathon Prototype → HUTCH Production |
| Version / date | **v1.2** · 2026-10-01 (see [CHANGES.md](CHANGES.md)) |
| Sources | (1) *Hutch Clarity* 17-slide deck - authoritative concept; (2) *HUTCH Hackathon Final Submission Guidelines* |
| Not available | SRS, architecture, API, DB, UML, infra, MCP, test, project, risk, RACI and cost documents. **All of these are created in this plan.** |
| Planning start | **2027-01-04 - Assumed project start date for planning purposes.** |
| LLM stance | Provider-neutral AI gateway with logical model **roles** (`fast-text`, `extract`, `reason`, …). Prototype: Gemini + Groq free tiers on synthetic, masked data only. Production: HUTCH's chosen provider or self-hosted models, by config. Model IDs live in config `[DECK S13]`; see [18 §4](18-tech-stack-and-ai.md). |

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
| [17-build-blueprint.md](17-build-blueprint.md) | Build Blueprint: baseline, modules, identity, data flow, notifications, MCP, module dependency graph, prototype Gantt | - |
| [18-tech-stack-and-ai.md](18-tech-stack-and-ai.md) | Enterprise tech stack, LLM providers (Gemini + Groq), AWS-style mapping, alignment of chapters 01–16 | - |
| [19-policy-change-management.md](19-policy-change-management.md) | Enterprise policy & change management: how packages, prices, regulations, caps, rules and wording change safely | - |
| [CHANGES.md](CHANGES.md) | Plan change record and the process for changing this plan | - |

## Reading paths

| Audience | Start with |
|---|---|
| Hackathon judges | [01](01-executive-summary-problem.md) → [05](05-architecture-diagrams.md) → [06](06-integration-tmf.md) → [13](13-delivery-plan.md) → [15](15-cost-scale-failure-kpi.md) → [16](16-gap-submission-repo-docs.md) |
| Solution architects / engineering | [17](17-build-blueprint.md), [18](18-tech-stack-and-ai.md), [19](19-policy-change-management.md), [04](04-enterprise-architecture.md), [05](05-architecture-diagrams.md), [09](09-rules-decision-receipts.md), [10](10-data-api-events.md), [12](12-platform-devops-testing-observability.md) |
| AI / MCP teams | [07](07-mcp.md), [08](08-ai-architecture.md), [15](15-cost-scale-failure-kpi.md) |
| Security & compliance | [11](11-security-privacy-audit.md), [07](07-mcp.md), [14](14-risk-pilot-readiness-operations.md) |
| CX, product, finance, business | [01](01-executive-summary-problem.md), [02](02-solution-capabilities.md), [03](03-requirements-personas-journeys.md), [09](09-rules-decision-receipts.md), [14](14-risk-pilot-readiness-operations.md) |
| Project management / DevOps / SRE | [13](13-delivery-plan.md), [12](12-platform-devops-testing-observability.md), [14](14-risk-pilot-readiness-operations.md) |

## Diagrams
All diagrams are written in Mermaid, which GitHub, GitLab and most Markdown viewers render. The full index of all 34 diagrams is in [05-architecture-diagrams.md § 8.1](05-architecture-diagrams.md#81-diagram-index-all-34-architecture-diagrams-in-this-plan).

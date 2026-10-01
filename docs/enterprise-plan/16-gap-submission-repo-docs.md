# Hutch Clarity — Prototype Gap, Hackathon Mapping, Repository, Documentation & Recommendations

[← 15-cost-scale-failure-kpi.md](15-cost-scale-failure-kpi.md) · [← Plan index](README.md) · [17-governance-compliance-change-cost.md →](17-governance-compliance-change-cost.md)

> Part of the **Hutch Clarity Enterprise Project Plan**. Labels: `[DECK Sx]` = stated in deck slide x · `[PROPOSED]` = expanded by this plan · **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION** / **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**. See the [index](README.md) for the full legend.

## 41. Prototype-to-Production Gap

| Area | Hackathon | Pilot | Production |
|---|---|---|---|
| Data | Synthetic/sample data `[DECK S4]` | Anonymized extracts → live read-only (shadow) → live | Live HUTCH data, governed retention |
| APIs | Mock services | HUTCH non-prod → prod read; approved writes | All approved interfaces; contract-tested |
| AI | Single model, simple prompts | Gateway, self-hosted primary, eval gates | Tiered routing, fallback, continuous eval, drift monitoring |
| Security | Demo auth, dev keys | SSO/MFA, OTP, pen test, DPIA | Full controls, HSM keys, SIEM, annual pen test |
| Rules | Handful of rules, hard-coded thresholds | 16 rules with golden tests; four-eyes | Governed catalogue, replay, versioned policy bundles |
| MCP | Few read tools | L1/L2 + propose; OPA; audit | Full catalogue, profiles, abuse monitoring |
| Receipts | Dev Ed25519 key, local verify | KMS/HSM key, verify page | Key rotation, WORM anchors, regulator use |
| Deployment | docker-compose / single host | K8s prod cluster with flags | Multi-AZ/DC, DR, GitOps, canary |
| Monitoring | Logs | OTel, Grafana, Langfuse, alerts | SLOs, on-call, SIEM, business dashboards |
| Scale | Demo traffic | Pilot cohort | Modelled to 1M interactions/day ([§38](15-cost-scale-failure-kpi.md)) |
| Testing | Manual demo tests | SIT, UAT, pen test, perf | Continuous: regression, eval, chaos, DR drills |
| Channels | Web + simulated WhatsApp/SMS | Web/app/WhatsApp | + SMS/USSD, voice, guardian |

---

## 42. Hackathon Requirement Mapping

Status reflects **this repository**, which currently contains only the two source documents. Items marked "Team to confirm" may exist elsewhere.

| Requirement (Guidelines) | Hutch Clarity Artifact | Status | Remaining Work |
|---|---|---|---|
| Final solution / prototype | Working Why? journey + Desk + receipt verify (mocked integrations) | Team to confirm — not in this repo | Ensure end-to-end VAS_NO_CONSENT + duplicate-reload journeys run; label mocks clearly |
| Source code repository | Monorepo (§43) | Not in repo | Push code; tag final commit; no secrets |
| README | `README.md` with all mandated sections | Not started | Use the Guidelines §3 list: team, problem, features, stack, architecture, setup, run/test, APIs, limitations, third parties, AI models |
| Solution / technical document (PDF) | This plan, condensed to the Guidelines §8 structure | **Drafted (this plan)** | Export a concise PDF (exec summary → limitations) |
| Architecture diagram | Diagrams 1, 2, 7 (+ index [§8.1](05-architecture-diagrams.md)) | **Drafted (Mermaid)** | Render to PNG/PDF |
| HUTCH integration demonstration | Adapter layer with mock drivers + data-flow diagrams (7, 11) | Design drafted; demo team to confirm | Show the adapter switch (mock ↔ "HUTCH" stub) in the demo |
| Integration feasibility (5 items) | [§9.5](06-integration-tmf.md) table | **Drafted** | — |
| Implementation plan | [§26](13-delivery-plan.md)–[§32](13-delivery-plan.md) | **Drafted** | — |
| Gantt chart | Diagram 31 + [§28.1](13-delivery-plan.md) | **Drafted** | Render to image for PDF |
| AI usage declaration | §42.1 below | Draft | Team to fill actual models and coding assistants |
| AI / token / forecast assumptions | [§37](15-cost-scale-failure-kpi.md), [§38](15-cost-scale-failure-kpi.md), [§12.8–12.9](08-ai-architecture.md), §42.3 disclosure template, [§51](17-governance-compliance-change-cost.md) provenance | Draft (assumed values) | Replace with measured prototype numbers |
| Presentation deck | 17-slide deck exists; slide mapping in §42.4 | **Exists** | Add team name + track to the title; add a live-demo cue slide; optional appendix with Gantt + integration diagrams |
| Demo video (3–7 min) | Storyboard in §42.5 | Team to confirm | Record per storyboard: problem in the first 60 s, complete journeys, mocks labelled on screen |
| Test credentials / demo access | Demo URL + test users (customer OTP stub, agent, supervisor) | Team to confirm | Share separately, not in the repo |
| Known limitations | §42.2 below | Draft | Copy into README |
| Third-party disclosure | [§21](12-platform-devops-testing-observability.md) stack table | Draft | Add versions + licences to README |
| Final checklist | Guidelines §15 | — | Team name, track, university/batch, links tested |
| Testing & demonstration readiness | Checklist in §42.6 | Not started | Run the checklist before submission and before the live demo |

### 42.1 AI usage declaration (draft for the team to complete)

| Item | Response (draft) |
|---|---|
| AI model / platform(s) used | **[Team to complete]** Prototype model(s) and provider(s). Production design: provider-agnostic gateway; self-hosted open-weight tier + optional hosted tier. |
| Purpose of AI usage | Multilingual intake extraction, explanation, staff summaries, RAG answers, complaint clustering summaries, Foresight personas. **Not** used for decisions, amounts or actions. |
| AI-generated code used? | **[Team to complete: Yes/No + which assistants]** |
| External AI APIs used? | **[Team to complete]** |
| RAG / external knowledge? | Yes: catalogue, T&C, Gazette 2316/14, help content (prototype: sample documents) |
| Prompting approach | System + FACTS + CONTEXT + USER blocks; JSON output; verifier ([§12.4](08-ai-architecture.md)) |
| AI vs rule-based | Rule-based: timeline, causes, decisions, actions, receipts. AI: language, retrieval, clustering, simulation. |
| Fallback | Templates; handoff; fallback model tier |
| Known AI limitations | Sinhala/Tamil/Singlish quality varies; hallucination risk mitigated by the verifier; STT accuracy for si/ta; Foresight outputs are scenarios, not forecasts |

### 42.2 Known limitations (current concept)
1. No real HUTCH integration. All HUTCH systems are mocked, and real interfaces are unknown.
2. Rule thresholds and caps are illustrative and not validated by HUTCH Finance.
3. Token, cost and scale figures are assumptions.
4. Sinhala/Tamil PII name detection and STT quality are not yet measured.
5. Foresight is unvalidated (no backtest data) and its third-party licensing is pending.
6. The bill-shock model has no training data; prototype values are simulated.
7. Customer quotes in the deck are paraphrased public posts ("patterns, not statistics").
8. Impact figures are expected effects to be measured in a pilot.

### 42.3 AI / LLM disclosure template (Guidelines §6.1), completed with plan values
Prototype values must be **measured** (Langfuse/gateway logs) and replace the assumed values below before submission.

| Disclosure item | Response |
|---|---|
| AI/LLM provider | **[Team to complete for prototype]**. Production: provider-agnostic gateway. Self-hosted open-weight tier first; optional hosted tier on masked text ([§12.2](08-ai-architecture.md)). |
| Model name & version | **[Team to complete]**. Production candidates are chosen by evaluation; model IDs live in config `[DECK S13]`. |
| Purpose | Intake extraction, explanation in si/ta/en, staff summaries, cited RAG answers, Autopsy canonical summaries and labels, Foresight personas |
| LLM calls per journey | Structured Why? dispute: 1 (+0.2 judge). Free-text dispute: 2 (+0.2). Simple question: 0–1. Staff case: 2. Proactive or zero-contact: 0 ([§37.2](15-cost-scale-failure-kpi.md)) |
| Avg input tokens per request | ≈ 600–1,500 (small tier); ≈ 4,000–6,000 (reasoning tier) — **ASSUMPTION** |
| Avg output tokens per request | ≈ 80–550 (small; si/ta higher); ≈ 1,400–1,600 incl. reasoning — **ASSUMPTION** |
| Avg total tokens per request / interaction | ≈ 1,650–3,200 per customer journey; ≈ 2,100 average per interaction across the assumed mix — **ASSUMPTION** |
| Scalability example | 2,100 tokens × 10,000 interactions/day ≈ 21M tokens/day ([§38](15-cost-scale-failure-kpi.md)) |
| RAG / external knowledge | Yes: catalogue, T&C, Gazette 2316/14, help content, CX-approved answers; cited by source ID and version ([§12.5](08-ai-architecture.md)) |
| Prompting approach | Versioned system prompt + FACTS JSON + delimited CONTEXT and USER blocks; JSON output; few-shot per language ([§12.4](08-ai-architecture.md)) |
| AI-generated vs rule-based | **Rules:** timeline, causes, confidence, decisions, amounts, actions, receipts, reconciliation. **AI:** language, retrieval, clustering, simulation. |
| Fallback | Templates (works without the LLM `[DECK S7]`), fallback tier, human handoff ([§39](15-cost-scale-failure-kpi.md)) |
| Known limitations | si/ta/Singlish quality varies; hallucination is controlled by the verifier but not impossible; STT accuracy; PII name detection in si/ta script; Foresight is unvalidated until backtested |
| Indicative cost | [§37.4](15-cost-scale-failure-kpi.md) (illustrative unit prices) |

### 42.4 Presentation mapping (Guidelines §9: 10 recommended slides)

| Recommended slide | Deck slide(s) | Gap |
|---|---|---|
| 1. Title (solution, team, track) | S1 | **Add team name and selected track** |
| 2. The Problem | S2 | — |
| 3. The Insight | S3 | — |
| 4. The Solution | S3, S5, S6 | — |
| 5. How It Works | S4, S7, S12 | — |
| 6. Technology & AI | S13, S14, S8 | Add the AI/LLM disclosure summary (§42.3) |
| 7. Customer Journey | S5, S16 | Optionally add Before → During → After ([§6.7](03-requirements-personas-journeys.md)) |
| 8. Live Demo | S4 (animated walkthrough) | **Add a live-demo cue slide** that marks mocked integrations |
| 9. Impact | S16, S15 | Keep the "expected, measured in a pilot" label |
| 10. Future Vision | S17 | Optional appendix: Gantt (Diagram 31), integration (Diagram 7) |

### 42.5 Demo video storyboard (target 5–6 min; Guidelines §10: 3–7 min)

| Time | Scene | What to show |
|---|---|---|
| 0:00–0:45 | Problem + one-line solution | S2 quotes → "Explain every rupee. Fix it by rule. Prove it won't happen again." |
| 0:45–2:15 | Journey 1: VAS without consent | App Why? on −LKR 49 → evidence + ruled-out causes → one-tap fix → balance updated → Trust Receipt → scan QR → **Verified** |
| 2:15–3:00 | Journey 2: zero-contact duplicate reload | Simulated payment stream → auto-refund → SMS receipt (simulator). Label: *simulated stream*. |
| 3:00–4:00 | Clarity Desk | High-risk case → staff approval with MFA step-up → Teach once |
| 4:00–4:45 | Rules decide, the LLM explains | Rule version on the decision; verifier blocks a wrong number; switch the LLM off → template answer; MCP audit log shows `propose_action` only |
| 4:45–5:30 | Autopsy + integration | Clusters from multilingual complaints; adapter switch from mock to "HUTCH" stub |
| 5:30–6:00 | Roadmap + close | Shadow → Desk → Customer → Foresight; Gantt milestones |

On-screen labels throughout: **"Mocked HUTCH systems · synthetic data"**.

### 42.6 Testing & demonstration readiness checklist (Guidelines §11)
- ☐ Application starts from a clean clone using README steps (tested on a second machine)
- ☐ Main journey works end-to-end (Journey 1); Journey 2 and the Desk flow work
- ☐ All buttons and links in the demo path work; QR verify page reachable
- ☐ Mock services and demo data load automatically; reset script restores the demo state
- ☐ Test credentials (customer OTP stub, agent, supervisor) valid and **shared separately**
- ☐ No production or confidential data; no secrets committed (secret scan clean)
- ☐ Source code matches the submitted prototype (final commit tagged)
- ☐ LLM-off fallback works live (in case of network issues at the venue)
- ☐ Presentation and demo video links accessible to judges

---

## 43. Repository Structure

```text
hutch-clarity/
├── apps/
│   ├── web/                    # Next.js PWA: customer Why? module (web + app WebView), verify page
│   └── desk/                   # Next.js: Clarity Desk + Ops/insights console
├── services/
│   ├── bff-api/                # Edge-facing API for frontends
│   ├── orchestrator/           # Sessions, language, routing, handoff, confirmation tokens
│   ├── case-service/           # Case aggregate, state machine, outbox
│   ├── timeline-builder/
│   ├── rule-engine/            # Evaluator + predicate library + replay
│   ├── decision-policy/        # OPA bundles (rego) + policy tests
│   ├── tool-layer/             # Action registry, idempotency, compensations
│   ├── receipts/               # Receipt builder, signing client, render pool, verify API
│   ├── desk-api/               # Approvals, bulk fix, what-if, regulator pack
│   ├── reconciliation/
│   ├── channels/               # whatsapp/, sms/, ussd/ connectors
│   ├── autopsy/
│   └── foresight/              # Sandboxed; aggregates only
├── ai/
│   ├── gateway/                # Model router, quotas, provider clients
│   ├── pii/                    # Presidio + Sri Lankan recognizers, token vault client
│   ├── verifier/
│   ├── prompts/                # Versioned prompts per language
│   ├── retrieval/              # RAG ingestion + retriever
│   ├── models/                 # Bill-shock, merchant risk
│   └── evaluation/             # Golden sets si/ta/en/Singlish, harness, red-team
├── mcp/
│   └── server/                 # tools/ resources/ prompts/ auth/ policy/ schemas/ adapters/ audit/ idempotency/ tests/
├── rules/
│   ├── packs/                  # VAS_NO_CONSENT/v4.yaml ...
│   └── golden/                 # positive/negative/boundary/replay fixtures per rule version
├── integrations/
│   ├── framework/              # Adapter base, resilience, driver selection
│   ├── payments/  charging/  catalogue/  vas-consent/  usage-fup/  loans/  crm/  identity/  notifications/
│   └── mocks/                  # Mock HUTCH services + synthetic stream generators
├── packages/
│   ├── schemas/                # JSON Schema (TMF-shaped) → Pydantic + TS codegen
│   ├── events/                 # Event schemas (Avro/Protobuf) + registry config
│   └── ui/                     # Shared design system (si/ta/en, accessibility)
├── infra/
│   ├── terraform/
│   ├── helm/
│   ├── argocd/
│   └── docker-compose/         # Local stack
├── tests/
│   ├── e2e/  contract/  load/  chaos/  security/
├── docs/
│   ├── enterprise-plan/        # This plan, split by chapter
│   ├── adr/                    # Architecture Decision Records
│   ├── api/                    # OpenAPI specs
│   ├── mcp/                    # Tool specification
│   ├── runbooks/
│   └── submission/             # Tech doc PDF, AI declaration, token disclosure, diagrams PNG
├── .github/workflows/          # or .gitlab-ci.yml
├── CODEOWNERS
├── SECURITY.md
└── README.md
```

---

## 44. Documentation Plan

| Document | Owner | When |
|---|---|---|
| Architecture Decision Records (ADR-001 … e.g., rule/OPA split, outbox, AI gateway, pilot-in-prod) | SA | From Phase 0, continuous |
| Software Requirements Specification | BA/PO | M1 |
| Solution Architecture Document | SA | M2 |
| Interface Control Documents (per adapter) + TMF mapping | Integration | M2 → M4 |
| API documentation (OpenAPI 3.1) | TL | Continuous, published per release |
| MCP tool specification (schemas, levels, profiles) | AI Lead | Phase 7 |
| Rule catalogue (human-readable, legal basis, owners) | CX Eng | Phase 5, per publish |
| Decision policy & approval matrix | Finance/PO | Phase 5 |
| Security model + threat model | Security | M2, updated at Security Gate |
| DPIA + privacy notice inputs | Compliance | Before shadow |
| Data dictionary + canonical model + retention schedule | Data Eng | M2 → M4 |
| AI evaluation report (per language) | AI Lead | Each model/prompt release |
| Test strategy + SIT report + performance report + pen-test report | QA/Security | Phases 14–15 |
| UAT plan and sign-off documents | BA/Business | Phase 16 |
| Runbooks + incident playbooks | SRE | Before pilot |
| DR plan + DR test report | SRE | Before go-live |
| Operations guide (support model, on-call, kill switches) | SRE | Before go-live |
| Training materials (agents, supervisors, finance, CX engineers) | CX Ops | Before Desk pilot |
| Pilot report + Production Readiness Review pack | PM | P18, R1 |
| Regulator pack specification (with TRCSL expectations) | Compliance | Phase 10 |
| Hackathon submission set (README, tech PDF, AI declaration, token disclosure) | Team | Now |
| Governance charter & stage-gate criteria | PM | G0 ([§46](17-governance-compliance-change-cost.md)) |
| Release plan & requirements traceability matrix | PO / BA | M1, maintained ([§47](17-governance-compliance-change-cost.md)) |
| Regulatory & compliance matrix | Compliance | M2 ([§48](17-governance-compliance-change-cost.md)) |
| Change management, training & communications plan | CX Ops | Before shadow ([§49](17-governance-compliance-change-cost.md)) |
| Effort & TCO model | PM + Finance | G0, refreshed per gate ([§50](17-governance-compliance-change-cost.md)) |
| Assumptions register & data provenance | PM | Continuous ([§51](17-governance-compliance-change-cost.md)) |
| Support model, hypercare & knowledge transfer plan | SRE + PO | Before G8 ([§52](17-governance-compliance-change-cost.md)) |
| Flow catalogue (self-service flows, versions, owners) | CX Eng | R2 ([§3.8](02-solution-capabilities.md)) |

---

## 45. Final Recommendations

1. **Keep the money boundary absolute.** Only deterministic rules, OPA policy and the tool layer move money. The LLM proposes and explains. MCP never exposes an execute path ([§10](07-mcp.md)–[§11](07-mcp.md)).
2. **Start read-only.** Shadow mode needs only read interfaces and anonymized data. It is the fastest, lowest-risk way to prove value and earn write access.
3. **Secure HUTCH dependencies in week 1.** Named owners for the 8 sources, the action policy workshop, the hosting decision and the pen-test slot. These control the critical path ([§29](13-delivery-plan.md)).
4. **Begin with high-precision, money-back-only rules** (DUPLICATE_RELOAD, VAS_NO_CONSENT, DUPLICATE_VAS_CHARGE) for auto/one-tap. Keep everything else staff-approved until override rates prove precision.
5. **Treat Sinhala/Tamil quality as a first-class workstream.** Native-speaker evaluation, structured-first UX and template fallback per language.
6. **Make receipts real proof.** HSM/KMS keys, public verification, WORM anchoring and supersede-not-edit.
7. **Run AI cost-aware from day one.** Templates and cache first, the self-hosted small model by default, and the hosted reasoning tier for masked staff summaries. Measure and publish model calls avoided `[DECK S15]`.
8. **Position Foresight as advisory.** Licence review plus a backtest gate before any business use. "Scenarios, not certainties."
9. **Govern rules like code.** Golden tests, replay, four-eyes, signed bundles, and teach-once feeding the backlog.
10. **For the hackathon:** turn the prototype status rows in §42 into done items, fill in the AI declaration with real models, measure tokens in the prototype, and export Diagrams 1, 2, 7 and 31 as images for the technical PDF.
11. **Run the project through formal governance.** Stage gates G0–G9, a living assumptions register and requirements traceability ([§46–§51](17-governance-compliance-change-cost.md)). Proactive care stays consent-, quiet-hours- and frequency-capped ([§3.6](02-solution-capabilities.md)), and reconciliation is a finance-owned daily control ([§14.4](09-rules-decision-receipts.md)).

### 45.1 Assumptions & HUTCH confirmations (consolidated; the full register with owners and dates is in [§51](17-governance-compliance-change-cost.md))
- **ASSUMPTION:** start date 2027-01-04; change freezes; cohort sizes; retention periods; token/traffic mix; unit prices; GPU throughput; thresholds and caps; candidate rule list.
- **REQUIRES HUTCH CONFIRMATION:**
  - existence, owners and interfaces of every HUTCH system category;
  - refund mechanism (reversal vs credit);
  - SIM-swap signal; WhatsApp identity policy;
  - warehouse platform (Snowflake?); hosting and K8s platform; GPU availability; data residency;
  - CAB process; legal basis and retention under PDPA;
  - TRCSL reporting expectations; pilot-in-production acceptability.
---

[← 15-cost-scale-failure-kpi.md](15-cost-scale-failure-kpi.md) · [← Plan index](README.md) · [17-governance-compliance-change-cost.md →](17-governance-compliance-change-cost.md)

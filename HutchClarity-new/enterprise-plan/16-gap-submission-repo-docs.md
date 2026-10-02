# Hutch Clarity - Prototype Gap, Hackathon Mapping, Repository, Documentation & Recommendations

[← 15-cost-scale-failure-kpi.md](15-cost-scale-failure-kpi.md) · [← Plan index](README.md)

> Part of the **Hutch Clarity Enterprise Project Plan**. Labels: `[DECK Sx]` = stated in deck slide x · `[PROPOSED]` = expanded by this plan · **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION** / **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**. See the [index](README.md) for the full legend.

> **Plan v1.1 (2026-10-01).** Updated to match [17](17-build-blueprint.md), [18](18-tech-stack-and-ai.md) and [19](19-policy-change-management.md). Change record: [CHANGES.md](CHANGES.md).

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
| Final solution / prototype | Working Why? journey + Desk + receipt verify (mocked integrations) | Team to confirm - not in this repo | Ensure end-to-end VAS_NO_CONSENT + duplicate-reload journeys run; label mocks clearly |
| Source code repository | Monorepo (§43) | Not in repo | Push code; tag final commit; no secrets |
| README | `README.md` with all mandated sections | Not started | Use the Guidelines §3 list: team, problem, features, stack, architecture, setup, run/test, APIs, limitations, third parties, AI models |
| Solution / technical document (PDF) | This plan, condensed to the Guidelines §8 structure | **Drafted (this plan)** | Export a concise PDF (exec summary → limitations) |
| Architecture diagram | Diagrams 1, 2, 7 (+ index [§8.1](05-architecture-diagrams.md)) | **Drafted (Mermaid)** | Render to PNG/PDF |
| HUTCH integration demonstration | Adapter layer with mock drivers + data-flow diagrams (7, 11) | Design drafted; demo team to confirm | Show the adapter switch (mock ↔ "HUTCH" stub) in the demo |
| Integration feasibility (5 items) | [§9.5](06-integration-tmf.md) table | **Drafted** | - |
| Implementation plan | [§26](13-delivery-plan.md)–[§32](13-delivery-plan.md) | **Drafted** | - |
| Gantt chart | Diagram 31 + [§28.1](13-delivery-plan.md) | **Drafted** | Render to image for PDF |
| AI usage declaration | §42.1 below | Draft | Team to fill actual models and coding assistants |
| AI / token / forecast assumptions | [§37](15-cost-scale-failure-kpi.md), [§38](15-cost-scale-failure-kpi.md), [§12.8](08-ai-architecture.md) | Draft (assumed values) | Replace with measured prototype numbers |
| Presentation deck | 17-slide deck exists | **Exists** | Ensure slide order covers the Guidelines' 10 slides (title needs team name + track) |
| Demo video (3–7 min) | - | Team to confirm | Problem in the first 60 s; one complete journey |
| Test credentials / demo access | Demo URL + test users (customer OTP stub, agent, supervisor) | Team to confirm | Share separately, not in the repo |
| Known limitations | §42.2 below | Draft | Copy into README |
| Third-party disclosure | [§21](12-platform-devops-testing-observability.md) stack table | Draft | Add versions + licences to README |
| Final checklist | Guidelines §15 | - | Team name, track, university/batch, links tested |

### 42.1 AI usage declaration (draft for the team to complete)

| Item | Response (draft) |
|---|---|
| AI model / platform(s) used | **Prototype:** Google Gemini API (free tier): Flash-Lite for fast text and extraction, Flash as reasoning fallback, Flash-Lite TTS. Groq (free tier): gpt-oss-120b (reasoning), gpt-oss-20b (fast fallback, judge), Whisper large-v3 (STT), Prompt Guard (preview). Self-hosted BGE-M3 embeddings. Exact IDs in `config/ai/models.yaml` ([18 §4](18-tech-stack-and-ai.md)). **Production:** provider chosen by HUTCH, by config. |
| Purpose of AI usage | Multilingual intake extraction, explanation, staff summaries, RAG answers, complaint clustering summaries, Foresight personas. **Not** used for decisions, amounts or actions. |
| AI-generated code used? | **[Team to complete: Yes/No + which assistants]** Note: plan chapters 17–19 and the repository governance files were drafted with Claude Code (Anthropic) and reviewed by the team. |
| External AI APIs used? | Yes: Gemini API and GroqCloud, free tiers, with **synthetic, PII-masked data only**; Groq Zero Data Retention enabled. |
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
9. The prototype uses free-tier LLM APIs: rate limits apply, and Gemini's free tier may use prompts for product improvement, so only synthetic data is used.

---

## 43. Repository Structure (v1.1)

Aligned with the build blueprint ([17 §2, §4](17-build-blueprint.md)). The planning folder `enterprise-plan/` stays at the repository root.

```text
hutch-clarity/
├── AGENTS.md  CLAUDE.md  ARCHITECTURE.md  CONTRIBUTING.md  CHANGELOG.md  SECURITY.md  README.md
├── enterprise-plan/              # This plan (versioned; changes via enterprise-plan/CHANGES.md)
├── backend/                      # Python, uv workspace
│   ├── src/clarity/
│   │   ├── kernel/               # L0 shared kernel
│   │   ├── platform/             # L2 module system, db, outbox, bus, idempotency, audit, vault, config, flags, authz, telemetry
│   │   ├── integration/          # L1 ports/ + drivers/{mock,sandbox,hutch}/
│   │   ├── ai/                   # L3 gateway client, pii, verifier, prompts, rag
│   │   ├── modules/<module>/     # L4 domain/ application/ infrastructure/ api/ public.py events.py MODULE.md tests/
│   │   └── entrypoints/          # api, worker, stream, migrate
│   └── tests/                    # cross-module integration + architecture (import-linter) tests
├── services/                     # separately deployed: mcp/ signer/ ai-gateway/ channel-gateway/ hutch-sim/
├── frontend/
│   ├── apps/                     # customer-web/ console/ verify/
│   └── packages/                 # ui/ sdk/ i18n/ widget/
├── contracts/                    # openapi/ asyncapi/ jsonschema/ -> generated Pydantic + TypeScript
├── rules/                        # manifests/ detectors/ tables/ (ZEN JDM) golden/
├── config/                       # non-secret defaults, ai/models.yaml, policy defaults
├── templates/                    # notification + explanation templates (si/ta/en)
├── deploy/                       # compose/ helm/ opentofu/ docs/
├── tests/                        # e2e/ contract/ load/ security/ chaos/
├── docs/                         # adr/ devlog/ walkthroughs/ templates/ modules.md WALKTHROUGHS.md api/ runbooks/ submission/
├── scripts/                      # codegen and dev helpers
└── .github/                      # workflows/ CODEOWNERS pull_request_template.md
```

Every unit under `modules/`, `services/` and `frontend/apps/` has a `MODULE.md`. The documentation rules are in the root [AGENTS.md](../AGENTS.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## 44. Documentation Plan

| Document | Owner | When |
|---|---|---|
| **Living docs (from day 1):** `AGENTS.md`, `ARCHITECTURE.md`, `MODULE.md` per module, walkthroughs, devlog entries, ADRs, `CHANGELOG.md`, plan `CHANGES.md` | Every developer; Tech Lead reviews | Every PR (checked in review) |
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

### 45.1 Assumptions & HUTCH confirmations (consolidated)
- **ASSUMPTION:** start date 2027-01-04; change freezes; cohort sizes; retention periods; token/traffic mix; unit prices; GPU throughput; thresholds and caps; candidate rule list.
- **REQUIRES HUTCH CONFIRMATION:**
  - existence, owners and interfaces of every HUTCH system category;
  - refund mechanism (reversal vs credit);
  - SIM-swap signal; WhatsApp identity policy;
  - warehouse platform (Snowflake?); hosting and K8s platform; GPU availability; data residency;
  - CAB process; legal basis and retention under PDPA;
  - TRCSL reporting expectations; pilot-in-production acceptability.
---

[← 15-cost-scale-failure-kpi.md](15-cost-scale-failure-kpi.md) · [← Plan index](README.md)

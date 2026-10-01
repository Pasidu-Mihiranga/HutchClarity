# Hutch Clarity — Executive Summary & Problem Analysis

[← Plan index](README.md) · [02-solution-capabilities.md →](02-solution-capabilities.md)

> Part of the **Hutch Clarity Enterprise Project Plan**. Labels: `[DECK Sx]` = stated in deck slide x · `[PROPOSED]` = expanded by this plan · **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION** / **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**. See the [index](README.md) for the full legend.

## 1. Executive Summary

### 1.1 What Hutch Clarity is
Hutch Clarity is one resolve-and-support platform for HUTCH customers and staff `[DECK S1]`. It works on hutch.lk, the Hutch app, WhatsApp, SMS/USSD and the staff console (Clarity Desk). For any charge, it:
- **explains** the exact cause with evidence, and says which causes were ruled out;
- **fixes** known causes by deterministic rule;
- **proves** the fix with a signed, QR-verifiable Trust Receipt;
- **prevents** recurrence by switching on a safeguard and, later, through Autopsy and Foresight.

### 1.2 Customer problem
Money moves and nobody can say why `[DECK S2]`. Examples: reloads taken twice, surprise VAS debits, "unlimited" data that stops at a hidden fair-use cap, and support that never replies. Customers can see balances and *5510# (last 5 events, data only as of midnight). They cannot see the **reason** for a deduction, a **single case file**, a **safe automatic fix**, a **receipt** after correction, or the **same answer on every channel** `[DECK S2]`.

### 1.3 Operational problem
- **Fragmented evidence.** The facts are spread across payment, charging, catalogue, consent and usage logs `[DECK S3]`, so agents must check several systems by hand.
- **No guardrail for automation.** There is no safe, rule-governed way to automate corrections, so every refund is manual.
- **Insight doesn't reach the frontline.** Analytics insight never reaches the chat ("Snowflake insight 12 h → 6 h never reaches the chat") `[DECK S2]`.
- **Unmanaged regulatory exposure.** VAS needs consent and OTP under Gazette 2316/14 `[DECK S3]`, and PDPA No. 9 of 2022 applies `[DECK S8]`.

### 1.4 Core solution
A deterministic **Clarity Core** does the work: Timeline Builder → Cause Detectors (versioned rules) → Decision Policy → idempotent Tool Layer → Trust Receipt. Language AI wraps the core for multilingual intake and explanation `[DECK S7, S12]`. Three surrounding capabilities turn single fixes into system improvement:
- **Complaint Autopsy:** clusters → root causes → self-service flows.
- **Foresight:** pre-launch simulation.
- **Clarity Desk:** staff cockpit, bulk fixes and governance.

**Design principle (non-negotiable): Rules decide. The LLM explains.** `[DECK S7]`

### 1.5 Primary users
- Prepaid customers on smartphones, WhatsApp or basic phones.
- Family guardians.
- HUTCH support agents and supervisors.
- CX analysts, finance/refund approvers and the VAS operations team.
- Network ops, product managers, and compliance/regulatory staff (see [§5](03-requirements-personas-journeys.md)).

### 1.6 Differentiators
1. **Evidence-first answers.** Text is a hint, never evidence `[DECK S7]`.
2. **Acting, not advising.** Safe causes are fixed in one tap or with no contact at all `[DECK S5]`.
3. **Cryptographic proof.** Receipts are Ed25519-signed, hash-chained and QR-verifiable `[DECK S6]`.
4. **Works without the LLM.** Templates cover the failure case, and a missing log goes to a human, never a guess `[DECK S7]`.
5. **Learns from the complaint stream** (Autopsy) and **from the future** (Foresight) `[DECK S11]`.
6. **Plug in, don't rip out.** TM Forum-shaped adapters and shadow mode come first `[DECK S14]`.

### 1.7 Expected enterprise value (to be measured in pilot, not claimed)
Every effect listed on slide 16 is an "expected effect, measured in a pilot" `[DECK S16]`:
- shorter resolution time, fewer complaints and less bill shock;
- more self-service and higher satisfaction;
- lower churn, lower cost to serve and reduced regulatory risk.

This plan sizes **none** of these. KPIs and baselines are defined in [§40](15-cost-scale-failure-kpi.md) and validated in the pilot ([§34](14-risk-pilot-readiness-operations.md)).

### 1.8 Current Hackathon Concept vs Proposed Enterprise Implementation

| Dimension | **Current Hackathon Concept** (deck) | **Proposed Enterprise Implementation** (this plan) |
|---|---|---|
| Data | Sample data, animated walkthrough `[DECK S4]` | Approved HUTCH interfaces via adapter layer. Anonymized data in shadow mode. Live events via Kafka. |
| Integrations | Named categories: Payments, Charging, Catalogue, VAS consent, Usage/FUP, Tickets `[DECK S12]` | Contract-tested adapters with a TMF-shaped canonical model, mTLS, read-first and write-only via the tool layer. Each one **REQUIRES HUTCH CONFIRMATION**. |
| Rules | "16 versioned cause rules" `[DECK S7]` | Rule catalogue under change control: golden tests, replay, four-eyes publishing. |
| Decisions | Outcome matrix (auto / one-tap / staff / explain / hand-off) `[DECK S7]` | OPA-evaluated decision policy with caps, refund budgets, SIM-swap and fraud signals, and daily reconciliation. |
| AI | Reasoning and non-reasoning LLMs, TTS, embeddings `[DECK S13]` | AI gateway, self-hosted model, hosted fallback, PII masking, deterministic verifier and an evaluation harness. |
| MCP | "MCP tools; tools need confirmation" `[DECK S13]` | Hutch Clarity MCP server with 4 safety levels. The LLM can only *propose* financial actions ([§11](07-mcp.md)). |
| Receipts | Ed25519, hash-chain, QR, PNG/PDF/SMS `[DECK S6]` | HSM/KMS-backed signing service, public verification endpoint, key rotation and WORM anchoring. |
| Security | WAF, OTP, SSO/MFA, RBAC, PII masking, KMS, audit ledger, SIEM `[DECK S8]` | Full threat model, network zoning, service identities, an ASVS L2 baseline and a PDPA DPIA. |
| Deployment | Docker, K8s, CI, OTel `[DECK S13]` | Six environments, GitOps, progressive delivery, feature flags and DR. |
| Rollout | Shadow → Desk live → Customer launch → Foresight & scale `[DECK S17]` | Gated pilot with entry/exit criteria ([§34](14-risk-pilot-readiness-operations.md)) and a production readiness review ([§35](14-risk-pilot-readiness-operations.md)). |

### 1.9 Prototype scope vs future production scope
This repository holds no prototype code. The left column is the **recommended minimum prototype scope** for the hackathon; the team confirms what was actually built. The right column is the scope this plan takes to production.

| Area | Hackathon prototype scope (recommended minimum) | Future production scope |
|---|---|---|
| Journeys | VAS without consent (one tap), duplicate reload (zero contact, simulated stream), FUP explain-only, high-risk case to staff approval | All 6 journeys in [§6](03-requirements-personas-journeys.md), plus proactive care and guardian mode |
| Channels | Web/app Why? module. WhatsApp via test number or simulator. SMS/USSD simulator. | hutch.lk, Hutch app WebView, WhatsApp (text + voice), SMS/USSD short code, shops |
| Data | Synthetic subscribers, packs, charges, payments, consents and complaints (labelled *simulated*) | Approved HUTCH interfaces and anonymized history |
| Rules | 4–6 of the 16 candidate rules, with golden tests | Governed catalogue of 16+ rules with replay and four-eyes publishing |
| AI | One model behind the gateway; templates; numeric verifier; masked prompts | Tiered routing, self-hosted primary, hosted fallback, continuous evaluation |
| MCP | L1 read tools + `propose_action` with UI confirmation | Full catalogue, 3 profiles, OPA authorization, abuse monitoring |
| Trust Receipt | Dev Ed25519 key, QR, public verify page | HSM/KMS keys, rotation, WORM anchoring |
| Autopsy | Clustering a synthetic multilingual complaint set | Weekly production runs with approval workflow |
| Foresight | One illustrative scenario, clearly marked as model-generated | Backtested service on aggregates only (2028) |
| Out of prototype scope | Real HUTCH integration, real customer data, production security, guardian mode, postpaid | Postpaid and home broadband in Step 4 `[DECK S17]` |

---

## 2. Problem Analysis

| # | Problem | Root Cause (evidence from deck; HUTCH internals **REQUIRE CONFIRMATION**) | Customer Impact | HUTCH Impact | Hutch Clarity Capability |
|---|---|---|---|---|---|
| P1 | Disputed / duplicate reloads | Bank/gateway debit and balance credit sit in separate systems with no joined view `[DECK S2, S12]` | Money gone, zero balance ("3,500 taken twice") | Manual refunds, chargebacks, repeat contacts | Timeline joins Payments + Charging. `DUPLICATE_RELOAD` and `RELOAD_NOT_CREDITED` rules. Zero-contact refund `[DECK S5]`. |
| P2 | Unexplained balance deductions | Charging reasons are not exposed. *5510# shows only the last 5 events, with data as of midnight `[DECK S2]`. | Distrust; feels like theft | Contacts, quiet churn | **Why?** button. Cause with evidence plus ruled-out causes `[DECK S5, S7]`. |
| P3 | VAS without proper consent | DCB/VAS charge with no OTP/second confirmation, contrary to Gazette 2316/14 `[DECK S3, S7]` | Surprise recurring debit | Regulatory exposure, merchant abuse, VAS revenue risk | `VAS_NO_CONSENT` rule. Refund + deactivate + block merchant until opt-in. Merchant watch `[DECK S7, S9]`. |
| P4 | Pack / FUP confusion | FUP cap and after-cap speed not visible at purchase; "unlimited" wording `[DECK S2, S5]` | Data stops "with 4 days left" | Perceived mis-selling, complaints | Pack truth label. `FUP_CAP_REACHED` (explain-only if shown at purchase). 80%/95% alerts `[DECK S5–S7]`. |
| P5 | Post-pack balance burn / bill shock | Data continues on main balance after the pack ends `[DECK S6]` | "LKR 480 burned the same way last month" (*illustrative*) | Refund requests, dissatisfaction | Bill-shock risk. Pack-end choice: stop data / cap spend / top up `[DECK S5, S6]`. |
| P6 | Inconsistent support answers | No shared rule outcome; each agent or channel interprets separately `[DECK S2]` | Different answers each time | Escalations, rework | One case file, one rule result, same receipt for staff and customer `[DECK S5]`. |
| P7 | Fragmented logs | 8 data sources across separate systems `[DECK S7]` | Slow answers | High handling time | Timeline Builder (8 sources → 1 case file). |
| P8 | Slow complaint resolution | No safe automation; manual queue ("4 WhatsApps + email, no reply after a week") `[DECK S2]` | Waits of days | Backlog, cost | Auto-fix / one-tap, smart queue, fix-all-like-this `[DECK S7, S9]`. |
| P9 | Cross-channel inconsistency | Sessions and cases are channel-specific | Repeats story; restarts | Duplicate cases | Channel-agnostic case. "Start on WhatsApp, finish in the app or at a shop" `[DECK S5]`. |
| P10 | No explainable transaction evidence | No receipt after a correction; regulator trail is manual | Cannot prove what happened | TRCSL queries, disputes reopen | Trust Receipt (signed, QR). Regulator pack `[DECK S6, S9]`. |
| P11 | Insight doesn't reach the frontline | Analytics latency (12 h → 6 h) is not connected to conversations `[DECK S2]` | Not warned early | Spikes overwhelm queues | Kafka early-warning radar, Autopsy, proactive care `[DECK S6, S11]`. |
| P12 | Launch-induced complaint spikes | Changes are not rehearsed before release | Sudden surprises | Reactive firefighting | Foresight scenario rehearsal; migration cards ready before launch `[DECK S11]`. |
---

[← Plan index](README.md) · [02-solution-capabilities.md →](02-solution-capabilities.md)

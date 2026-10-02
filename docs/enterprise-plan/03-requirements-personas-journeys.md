# Hutch Clarity - Requirements, Personas & Customer Journeys

[← 02-solution-capabilities.md](02-solution-capabilities.md) · [← Plan index](README.md) · [04-enterprise-architecture.md →](04-enterprise-architecture.md)

> Part of the **Hutch Clarity Enterprise Project Plan**. Labels: `[DECK Sx]` = stated in deck slide x · `[PROPOSED]` = expanded by this plan · **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION** / **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**. See the [index](README.md) for the full legend.

> **Plan v1.3 (2026-10-02).** Merged plan: updated to match [18](18-build-blueprint.md), [19](19-tech-stack-and-ai.md), [20](20-policy-change-management.md) and [21](21-migration-and-deployment-plan.md). Change record: [CHANGES.md](CHANGES.md).

## 4. Requirements Engineering

### 4.1 Functional Requirements
Priority: **Must / Should / Could / Future**. Columns Prototype/Production: ✅ in scope · ◐ simulated/partial · - not in scope.

| ID | Module | Requirement | Actor | Priority | Prototype | Production |
|---|---|---|---|---|---|---|
| FR-COP-01 | Copilot | Customer can tap **Why?** on any charge in web/app and receive a cause with evidence | Prepaid customer | Must | ✅ (mock data) | ✅ |
| FR-COP-02 | Copilot | Accept free-text or voice questions in Sinhala, Tamil, English, Singlish | Customer | Must | ◐ text | ✅ |
| FR-COP-03 | Copilot | Build a timeline from up to 8 sources for a bounded window | System | Must | ◐ mock adapters | ✅ |
| FR-COP-04 | Copilot | Evaluate all active cause rules; return ranked and ruled-out causes | System | Must | ✅ | ✅ |
| FR-COP-05 | Copilot | Apply decision policy (auto / one-tap / staff / explain / handoff) | System | Must | ✅ | ✅ |
| FR-COP-06 | Copilot | Execute customer-confirmed actions idempotently | System | Must | ◐ mock | ✅ |
| FR-COP-07 | Copilot | Explanation numbers verified against facts; template fallback | System | Must | ✅ | ✅ |
| FR-COP-08 | Copilot | Handoff to Desk with full trail and reason code on every turn | System | Must | ✅ | ✅ |
| FR-COP-09 | Copilot | Zero-contact refund of duplicate reload from the live event stream | System | Should | ◐ simulated stream | ✅ (whitelisted) |
| FR-COP-10 | Copilot | Pack truth label (FUP cap, after-cap speed, apps) before purchase | Customer | Should | ◐ | ✅ |
| FR-COP-11 | Copilot | Pack-end choice: stop data / cap spend / top up | Customer | Should | ◐ | ✅ |
| FR-COP-12 | Copilot | Proactive alerts: FUP 80/95%, VAS renewal, bill-shock risk, outage ETA | System | Should | ◐ | ✅ |
| FR-COP-13 | Copilot | Family guardian for up to 10 numbers with consent of each member | Guardian | Could | - | ✅ (Phase 4) |
| FR-COP-14 | Copilot | Customer preferences: language, answer length, large text | Customer | Should | ◐ | ✅ |
| FR-COP-15 | Copilot | Spoken answer back (TTS) in Sinhala/Tamil for voice-note users `[DECK S5]` | Customer | Should | - | ✅ |
| FR-CH-01 | Channels | Web (hutch.lk) and Hutch app WebView module | Customer | Must | ✅ | ✅ |
| FR-CH-02 | Channels | WhatsApp text and voice notes | Customer | Must | ◐ sandbox | ✅ |
| FR-CH-03 | Channels | SMS/USSD short code returns reason by SMS | Basic-phone customer | Should | ◐ simulator | ✅ |
| FR-CH-04 | Channels | One case continues across channels and shops | Customer, agent | Must | ◐ | ✅ |
| FR-CH-05 | Channels | Shop staff can open, continue and close a customer's case with the same trail and receipt `[DECK S5]` | Shop staff | Should | - | ✅ |
| FR-TR-01 | Receipt | Issue a Trust Receipt for every action and explain-only decision | System | Must | ✅ | ✅ |
| FR-TR-02 | Receipt | Ed25519 signature + hash chain | System | Must | ✅ (dev key) | ✅ (HSM/KMS) |
| FR-TR-03 | Receipt | QR public verification page | Anyone | Must | ✅ | ✅ |
| FR-TR-04 | Receipt | Render si/ta/en as PNG, PDF and SMS | System | Must | ◐ | ✅ |
| FR-TR-05 | Receipt | Recurrence test result based on a post-action check | System | Should | ◐ | ✅ |
| FR-TR-06 | Receipt | Replay the decision from the evidence snapshot | Staff, auditor | Should | ◐ | ✅ |
| FR-TR-07 | Receipt | Agents, shop staff and authorised verifiers can look up and verify a receipt by ID (1788, WhatsApp, shop, TRCSL) `[DECK S6]` | Agent, shop staff, verifier | Must | ◐ | ✅ |
| FR-AUT-01 | Autopsy | Ingest complaints from all contact channels | System | Must | ◐ synthetic | ✅ |
| FR-AUT-02 | Autopsy | Dedupe, detect language and mask PII before AI | System | Must | ✅ | ✅ |
| FR-AUT-03 | Autopsy | Canonical summary + multilingual embedding + UMAP/HDBSCAN clustering | System | Must | ✅ | ✅ |
| FR-AUT-04 | Autopsy | Map clusters to rule hits and propose root cause | CX analyst | Should | ◐ | ✅ |
| FR-AUT-05 | Autopsy | Draft self-service flow from real checks; replay; approve; publish | CX analyst, approver | Should | ◐ | ✅ |
| FR-FOR-01 | Foresight | Define scenario from catalogue/price/policy/outage change | Product manager | Should | ◐ | ✅ (Step 4) |
| FR-FOR-02 | Foresight | Simulate aggregated personas and output predicted complaint themes | System | Should | ◐ | ✅ |
| FR-FOR-03 | Foresight | Backtest against past launches; show uncertainty | AI team | Must (before production use) | - | ✅ |
| FR-FOR-04 | Foresight | Live early-warning spike radar | Supervisor | Should | ◐ | ✅ |
| FR-DSK-01 | Desk | Smart queue sorted by money, repeats, frustration | Agent | Must | ✅ | ✅ |
| FR-DSK-02 | Desk | Case cockpit with evidence, ranked causes, ruled-out causes | Agent | Must | ✅ | ✅ |
| FR-DSK-03 | Desk | One-click policy-checked action; approvals with MFA step-up | Agent, supervisor | Must | ◐ | ✅ |
| FR-DSK-04 | Desk | Multilingual reply drafting with verifier | Agent | Must | ◐ | ✅ |
| FR-DSK-05 | Desk | Teach once → test case + rule proposal | Agent, CX engineer | Should | ◐ | ✅ |
| FR-DSK-06 | Desk | Fix all like this (bulk) with four-eyes and per-case receipts | Supervisor, finance | Should | - | ✅ |
| FR-DSK-07 | Desk | Second look review | Supervisor | Could | - | ✅ |
| FR-DSK-08 | Desk | Policy what-if replay | CX engineer, finance | Should | ◐ | ✅ |
| FR-DSK-09 | Desk | Merchant watch scoring and suspension request | VAS ops | Should | - | ✅ |
| FR-DSK-10 | Desk | Shift handover summary | Supervisor | Could | ◐ | ✅ |
| FR-DSK-11 | Desk | Regulator pack export (trail + consents) | Compliance | Must | - | ✅ |
| FR-DSK-12 | Desk | Insights: where AI stops, self-service drops, slicing | CX analyst | Should | ◐ | ✅ |
| FR-DSK-13 | Desk | Mobile approval for supervisors | Supervisor | Could | - | ✅ |
| FR-GOV-01 | Governance | Rule/policy versions with four-eyes publishing and golden tests | CX engineer, approver | Must | ◐ | ✅ |
| FR-GOV-02 | Governance | Refund budgets and daily reconciliation | Finance | Must | ◐ | ✅ |
| FR-GOV-03 | Governance | Every customer- or money-affecting decision is auditable | Auditor | Must | ✅ | ✅ |
| FR-GOV-06 | Governance | Every policy artefact (parameters, decision tables, rule packs, templates, knowledge, catalogue mappings) is versioned, effective-dated, scoped, approved per change class and replayable ([20](20-policy-change-management.md)) | CX engineer, finance, compliance | Must | ✅ | ✅ |
| FR-GOV-07 | Governance | Scheduled activation and instant rollback of policy versions; emergency change path with post-hoc review | Approvers | Must | ◐ | ✅ |
| FR-GOV-08 | Governance | Impact preview before publish: replay of historic cases with outcome and money deltas | CX engineer, finance | Must | ✅ | ✅ |
| FR-ADM-01 | Admin | Admin console: feature flags and kill switches, configuration, templates, MCP client registry, adapter health, signing-key status, audit viewer | Platform admin | Must | ◐ | ✅ |
| FR-ADM-02 | Admin | Separation of duties: admins cannot approve money actions; a maker can never be the checker | System | Must | ✅ | ✅ |
| FR-GOV-04 | Governance | Kill switches per rule, per channel, for auto-fix globally and for LLM explanations | Supervisor, SRE | Must | ◐ | ✅ |
| FR-GOV-05 | Governance | Proactive messages respect consent, quiet hours and frequency caps ([§3.6](02-solution-capabilities.md)) | System | Must | ◐ | ✅ |
| FR-MCP-01 | MCP | AI accesses capabilities only through the Clarity MCP server allowlist | System | Must | ✅ | ✅ |
| FR-MCP-02 | MCP | Registered external MCP clients (e.g., HUTCH chatbot, agent assist) use profile-scoped tools via OAuth 2.1 over the MCP protocol; Why? and receipt cards render as MCP Apps UI | HUTCH systems | Should | ◐ | ✅ |
| FR-FUT-01 | Scale | Postpaid and home broadband domains | - | Future | - | Step 4 `[DECK S17]` |

### 4.2 Non-Functional Requirements
All numeric values are **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**.

| Category | ID | Requirement |
|---|---|---|
| Latency | NFR-PERF-01 | Why? (rules + template path) p95 ≤ 2.5 s end-to-end, excluding HUTCH adapter latency beyond its SLA |
| | NFR-PERF-02 | Why? with LLM explanation p95 ≤ 6 s; acknowledgement/typing indicator ≤ 1 s |
| | NFR-PERF-03 | Zero-contact duplicate-reload detection ≤ 5 min from `payment.recorded` to decision |
| | NFR-PERF-04 | Desk case cockpit load p95 ≤ 2 s |
| | NFR-PERF-05 | Receipt verification page p95 ≤ 800 ms |
| | NFR-PERF-06 | Why? web module initial load ≤ 200 KB compressed and usable on 3G-class connections and older app WebViews `[DECK S15]` (supported versions **REQUIRE HUTCH CONFIRMATION**) |
| Availability | NFR-AV-01 | Customer channels (Why?) 99.9% monthly. Tool layer 99.9%. Desk 99.9% in staffed hours. Verification page 99.95%. |
| Scalability | NFR-SC-01 | Stateless services scale horizontally. Kafka partitioned by hashed MSISDN token `[DECK S14]`. Model tested to 10× pilot load. |
| Security | NFR-SEC-01 | OWASP ASVS Level 2 for all services; Level 3 controls on tool layer, signing service and token vault |
| | NFR-SEC-02 | No secrets in code; all keys in KMS/HSM; mTLS between all internal services and adapters |
| Privacy | NFR-PRV-01 | No raw PII, OTP or card data leaves the HUTCH trust boundary to any external AI `[DECK S8]` |
| | NFR-PRV-02 | PDPA No. 9 of 2022 compliant processing, DPIA completed, retention schedule enforced. **REQUIRES HUTCH legal confirmation.** |
| | NFR-PRV-03 | Data residency: customer data, evidence and the token vault stay in HUTCH-approved locations. Only masked text may go to an approved hosted AI tier. **REQUIRES HUTCH CONFIRMATION.** |
| Observability | NFR-OBS-01 | 100% of requests traced (OTel). 100% of decisions log rule and policy version. LLM calls traced in Langfuse (masked). |
| Auditability | NFR-AUD-01 | Append-only hash-chained audit. Consent evidence kept ≥ 1 year `[DECK S8]`. Audit retention 7 years (**ASSUMPTION**; legal to confirm). |
| Correctness | NFR-COR-01 | **Zero** duplicate financial executions (hard invariant, enforced by idempotency + DB uniqueness). Reconciliation of 100% of actions by T+1. |
| Maintainability | NFR-MNT-01 | Rule changes need no code deploy (rule-pack publish). Every rule version has ≥ 95% branch coverage via golden tests. |
| Localization | NFR-L10N-01 | si, ta, en at launch: Unicode, correct shaping in receipts, numerals and LKR formats |
| Accessibility | NFR-ACC-01 | WCAG 2.2 AA for web/app/Desk. Large text. Voice in/out. SMS/USSD for basic phones `[DECK S15]`. |
| Reliability | NFR-REL-01 | Graceful degradation per [§39](15-cost-scale-failure-kpi.md). No financial action without confirmed evidence completeness. |
| DR | NFR-DR-01 | RPO ≤ 5 min (cases, actions, ledger), RTO ≤ 1 h. Restore tested quarterly. |
| Efficiency | NFR-EFF-01 | ≥ 50% of interactions answered without any LLM call (rules/templates/cache) `[DECK S14]` (*target*) |
| Cost | NFR-COST-01 | Average AI cost per interaction and a daily AI budget are tracked, with a per-session token cap ([§37](15-cost-scale-failure-kpi.md)) |

---

## 5. Personas

| Persona | Channel | Goals | Pains (deck) | Clarity features | Justification |
|---|---|---|---|---|---|
| **Dilani - prepaid smartphone customer** (Sinhala) | Hutch app, web | Know why money went; get it back fast | Surprise VAS debit; zero balance after reload | Why?, one-tap fix, receipt, safeguards | `[DECK S2, S5]` |
| **Kumar - WhatsApp-first customer** (Tamil, voice) | WhatsApp text + voice | Ask in his own language without an app | No reply after a week on WhatsApp | Voice note in/out, cross-channel case | `[DECK S2, S5]` |
| **Sunil - basic-phone customer** | SMS/USSD | Get reason without a smartphone | *5510# shows only last 5 events | Why? via short code, SMS receipt | `[DECK S5]` |
| **Ama - family guardian** | App | Protect parents/children numbers | Bill shock on family lines | Guardian mode (≤10), safeguards | `[DECK S5, S6]` |
| **Postpaid customer** | App/web | Understand bill line items | - | **Future** (Step 4) | `[DECK S17]` |
| **Nadeesha - support agent** | Clarity Desk | Resolve quickly with evidence | Fragmented logs | Cockpit, one-click fix, multilingual reply | `[DECK S9]` |
| **Ruwan - supervisor** | Desk + mobile | Approve, manage queue and shift | Backlog; handovers | Approvals, bulk fix, handover, second look | `[DECK S9]` |
| **Hutch shop / retail staff** | Clarity Desk (shop view) | Finish a case started on WhatsApp or the app; verify a receipt in front of the customer | Customer arrives with no trail | Case lookup (number + customer OTP), receipt verification, handoff | `[DECK S5]` "finish … at a shop". Whether shops are owned or franchised **REQUIRES HUTCH CONFIRMATION**. |
| **CX analyst / CX engineer** | Desk insights | Find gaps, write and test rules | Unknown root causes | Autopsy, teach once, what-if, funnels | `[DECK S10, S11]` |
| **Finance / refund approver** | Desk | Control refund risk and budget | Large disputed charges | Caps, budgets, approvals, reconciliation | `[DECK S7, S10]` |
| **VAS operations** | Desk | Clean merchants, consent compliance | Merchant abuse | Merchant watch, consent evidence | `[DECK S9, S10]` |
| **Network operations** | Ticket integration | Get precise fault reports | Vague complaints | Auto ticket with cell, time, ETA | `[DECK S10]` |
| **Product manager** | Foresight, insights | Launch without surprises | Launch complaint spikes | Foresight, product-fault alerts | `[DECK S10, S11]` |
| **Compliance / regulatory** | Desk | Prove consent and fairness to TRCSL | Manual evidence | Regulator pack, audit ledger | `[DECK S8, S9]` |
| **Platform admin / security admin** | Console `/admin` | Keep the platform configured, secure and auditable | (enterprise need) | Flags and kill switches, config, templates, MCP clients, adapter health, key status, audit viewer | `[PROPOSED]` |
| **External verifier** (TRCSL officer, auditor) | Public verify page, regulator pack | Confirm what happened and that consent rules were followed | Manual, slow evidence | QR verification, signed trail | `[DECK S6, S9]` |

---

## 6. Customer Journeys
Format: **User → Channel → Identity → Clarity → Timeline → Rule → Decision → Tool → Result → Trust Receipt**. All amounts are *illustrative*.

### 6.1 Unexplained deduction (VAS without consent, deck example `[DECK S6, S7]`)

| Stage | Detail |
|---|---|
| User | Dilani sees −LKR 49 and taps **Why?** |
| Channel | Hutch app WebView (Clarity module) |
| Identity | App session → Clarity exchanges the app token for a short-lived Clarity token (OTP if no session) |
| Clarity | Structured intake: `charge_ref` known → no LLM needed for intake |
| Timeline | Charging (LKR 49 at 14:06, merchant M), VAS consent (no OTP/second confirmation), Usage (3.2 GB left), Loans (none in 30 days) |
| Rule | `VAS_NO_CONSENT v4` matches (confidence 96%). Ruled out: `PACK_EXPIRY`, `LOAN_RECOVERY`. |
| Decision | Refund under cap, but a service change is involved → **Fix with one tap** |
| Tool | After the customer confirms: `refund(49)`, `vas.deactivate`, `merchant.block_until_optin` (idempotent, outbox) |
| Result | Balance 263.00 → 312.00. Recurrence check: merchant block active → PASSED. |
| Trust Receipt | TR-2026-000184-style receipt, si/ta/en, QR |

### 6.2 Duplicate reload (zero-contact)

| Stage | Detail |
|---|---|
| User | Pays LKR 3,500 for 90-day pack; bank debits twice `[DECK S2]` |
| Channel | None - detected from the event stream `[DECK S5]` |
| Identity | System principal `svc-stream-detector` |
| Clarity | `payment.recorded` × 2 for the same MSISDN token, amount and merchant ref within a window |
| Timeline | Payments (two gateway captures), Charging (one credit), Catalogue (pack price) |
| Rule | `DUPLICATE_RELOAD` (same bank ref family, Δt ≤ N min, single credit) |
| Decision | Money back only + high confidence + under cap + budget available → **Auto-fix** |
| Tool | `refund` via the payment-reversal adapter (**REQUIRES HUTCH CONFIRMATION** on whether reversal or balance credit is the approved remedy) |
| Result | Refund confirmed; SMS/WhatsApp notification |
| Trust Receipt | Issued automatically and linked in the notification |

### 6.3 VAS without proper consent (customer-initiated by WhatsApp voice)

| Stage | Detail |
|---|---|
| User | Kumar sends a Tamil voice note: "money cut, I didn't buy anything" |
| Channel | WhatsApp Cloud API → webhook → orchestration |
| Identity | WhatsApp number matched to MSISDN. OTP step-up before any action or account data (**REQUIRES HUTCH CONFIRMATION** of WhatsApp identity policy). |
| Clarity | STT (ta) → masked text → LLM extraction `{intent: unexplained_charge, date_hint: today}` (hint only) |
| Timeline | Charges for last 7 days; consent log; subscriptions |
| Rule | `VAS_NO_CONSENT` for 2 charges from merchant M; one other VAS has a valid OTP → ruled out |
| Decision | One-tap fix (service change) |
| Tool | Customer taps the WhatsApp interactive button → confirmation token minted by the orchestrator → tool layer executes |
| Result | Refund + deactivate + block. Spoken Tamil answer (TTS). |
| Trust Receipt | PDF + link in WhatsApp |

### 6.4 Pack / FUP confusion (explain only)

| Stage | Detail |
|---|---|
| User | "App says 4 days left, my unlimited data stopped" `[DECK S2]` |
| Channel | Web |
| Identity | OTP login |
| Clarity | Free-text Singlish → extraction (`intent: data_stopped`) |
| Timeline | Usage/FUP (cap reached at 14:00), PCRF policy change (throttle), catalogue version at purchase shows FUP disclosed |
| Rule | `FUP_CAP_REACHED` matches; disclosure shown at purchase = true |
| Decision | **Explain only** (rule the customer saw) `[DECK S7]` |
| Tool | None financial. Offer an add-on or enable an FUP alert at 80/95% (L2 safeguard with confirmation). |
| Result | Cited explanation (catalogue v-id, T&C clause) + safeguard |
| Trust Receipt | Explain-only receipt (no correction) |

### 6.5 High-risk case requiring staff approval

| Stage | Detail |
|---|---|
| User | Disputes LKR 12,000 reload not credited (*illustrative*) |
| Channel | App → later continued at a shop |
| Identity | OTP. Risk signals: SIM swap 2 days ago (**REQUIRES HUTCH CONFIRMATION** of SIM-swap signal source). |
| Clarity | Timeline: payment captured, charging credit missing, and the charging adapter reports a partial outage → evidence incomplete |
| Rule | `RELOAD_NOT_CREDITED` (confidence 71%) vs `PAYMENT_PENDING_SETTLEMENT` (66%): two causes close |
| Decision | Above cap + recent SIM swap + conflicting causes → **Staff approval** (and hold for evidence) |
| Tool | `create_support_case` with priority = money at stake |
| Result | Desk shows trail. Supervisor approves after evidence completes (MFA step-up); finance second approval above the higher threshold. |
| Trust Receipt | Issued after approved action; names the approver role (not the person) |

### 6.6 Proactive bill-shock warning `[DECK S6]`

| Stage | Detail |
|---|---|
| User | No action - Dilani's pack is 92% used, 2 days left |
| Channel | Push / WhatsApp template / SMS, by preference |
| Identity | System principal; customer's notification consent required |
| Clarity | `usage.threshold_reached` + `pack.expiring` events; bill-shock risk score (deterministic features + calibrated model) |
| Timeline | Last month: LKR 480 burned after pack end (*illustrative*) |
| Rule | `POST_PACK_BURN_RISK` (risk 78%, High) |
| Decision | Proactive offer: stop data / cap at LKR 100 / top up |
| Tool | Customer chooses "cap at 100" → `set_spend_cap` (L2, confirmed) |
| Result | Safeguard active; tracked against next month's burn |
| Trust Receipt | Safeguard receipt |

### 6.7 Before → During → After (Guidelines §8)
Summary of the change in experience, based on `[DECK S16]`. "After" effects are **expected effects to be measured in the pilot**, not claims.

| | Before (today) | During (with Clarity) | After (expected, to be measured) |
|---|---|---|---|
| **Customer** | Money gone with no reason; days waiting on WhatsApp or 1788; a different answer each time; surprise burn when a pack ends `[DECK S2, S16]` | Taps Why? or sends a voice note; gets the reason with evidence in seconds; fixes in one tap or gets a person with the full trail; receives a receipt in si/ta/en | Answer and fix in minutes; proof kept and the same story everywhere; a safeguard prevents repeats |
| **Agent / supervisor** | Checks several systems by hand; no safe automation; inconsistent outcomes | Case cockpit with evidence, ranked and ruled-out causes; one-click policy-checked fixes; replies in the customer's language | Lighter queue; Teach once improves rules; handovers and regulator packs are generated |
| **HUTCH** | Quiet churn, repeat contacts, regulatory exposure, launch surprises | Rules decide, the LLM explains, everything is audited | Validate in pilot: fewer complaints, lower cost to serve, VAS consent proof, launch issues found early |

---

[← 02-solution-capabilities.md](02-solution-capabilities.md) · [← Plan index](README.md) · [04-enterprise-architecture.md →](04-enterprise-architecture.md)

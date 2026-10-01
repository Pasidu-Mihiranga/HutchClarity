# Known Limitations — Hutch Clarity prototype

Required by the HUTCH Hackathon Final Submission Guidelines (§1, §3, §6.4).

Written plainly: a reviewer should be able to tell exactly where the prototype
stops and where production design begins, without reading the code.

---

## 1. Nothing here touches HUTCH

| | |
|---|---|
| **HUTCH systems** | All eight sources are **mock drivers** over a synthetic world. No HUTCH API, credential, sandbox or production system was used — none was available (Guidelines §4). |
| **Data** | Every subscriber, charge, payment, consent record and complaint is **generated**. Any resemblance to a real customer is coincidental. |
| **Interfaces** | The real shape of HUTCH's charging, payments, catalogue, VAS/DCB, usage and CRM interfaces is **unknown**. The adapter layer is designed so each driver is swappable by config, but no mapping has been validated. |
| **Proof** | `AdapterRegistry(mode=DriverMode.PRODUCTION)` deliberately raises `NotYetIntegrated` rather than pretending. |

## 2. Figures are illustrative, not measured

- Rule thresholds, refund caps and budgets (auto ≤ LKR 5,000, one-tap ≤ LKR 10,000, four-eyes above LKR 25,000) are **assumptions**. HUTCH Finance has not validated them.
- Confidence scores come from hand-set weights in the rule packs, not from calibration against outcomes.
- Foresight segment shares and complaint rates are **invented for the demo**.
- No business impact is claimed. The deck's impact figures are "expected effects, measured in a pilot" and remain unmeasured.

## 3. What is not built

| Area | State |
|---|---|
| **Persistence** | Everything is in memory. **A restart loses all cases and receipts.** |
| **Authentication** | Implemented, but the issuer is ours, not HUTCH's. Customers sign in by OTP and staff pick roles from a labelled simulated identity provider; the permission checks those feed are the production ones (deny by default, subject binding, step-up before money). The signing key is generated at startup, so a restart signs everyone out, and there is no refresh, revocation or session store. Production federates HUTCH SSO + MFA and the HUTCH OTP service (plan §19, ADR-0010). |
| **Language model** | None configured. Explanations come from templates — see [AI_DISCLOSURE.md](AI_DISCLOSURE.md). |
| **Retrieval (RAG)** | Designed, not implemented. Policy questions outside the rule set go to a human. |
| **Events to Kafka** | The outbox and envelope exist; the relay is in-process. No broker. |
| **Rules** | 6 of the 16 candidate rules in the plan. |
| **Channels** | Web only. WhatsApp, SMS and USSD are designed but not connected. |
| **Voice** | Not implemented. No STT or TTS. |
| **Family guardian** | Not implemented. |
| **Postpaid / home broadband** | Out of scope (Step 4 in the deck's roadmap). |

## 4. Where the quality is weakest

1. **Sinhala and Tamil wording has not been reviewed by native speakers.** The templates and UI copy were written for the demo. Plan §49.2 puts native review on the critical path before any customer sees them.
2. **PII name detection in Sinhala and Tamil script is weak.** Phone numbers, NICs, emails and passports are matched structurally and reliably; personal *names* in local script largely are not. Mitigated because the main journey is a structured "Why?" tap rather than free text, but it is a real gap.
3. **Complaint clustering uses character trigrams, not embeddings.** Good enough to demonstrate the pipeline; it will underperform on code-mixed Singlish, which is exactly where the plan's canonical-summary step matters.
4. **Foresight is uncalibrated.** It has never been backtested against a real launch, and says so in every report it produces.
5. **The decision policy is Python, not OPA.** Same input document and recorded version, but the production path is Rego bundles (plan §14.3).

## 5. Deliberate simplifications

Each was a judgment call, with the production design noted:

| Simplification | Why | Production |
|---|---|---|
| UI is plain HTML/JS served by FastAPI | One command to run, no Node toolchain for judges | Next.js + TypeScript + Tailwind (plan §21) |
| SQLite/PostgreSQL replaced by in-memory stores | Nothing in the demo needs durability | PostgreSQL 16 + pgvector |
| In-process event relay | No broker to run | Kafka + Schema Registry |
| Dev Ed25519 key on disk | No HSM available | HSM/KMS signing service (plan §15.2) |
| Decision policy in Python | Avoids an OPA sidecar | OPA/Rego bundles |

## 6. What the prototype does demonstrate honestly

So the limitations above are not read as "nothing works":

- The complete journey — evidence → cause → decision → confirmation → action → signed receipt → public verification — runs end to end.
- Receipts are genuinely signed and genuinely verifiable; a tampered or forged one fails.
- The recurrence test re-reads live state, so "PASSED" means the merchant block really is in place.
- The LLM boundary is structural: there is no code path by which a model can execute a financial action, and tests assert it.
- 300+ tests, `ruff` and `mypy --strict` clean.

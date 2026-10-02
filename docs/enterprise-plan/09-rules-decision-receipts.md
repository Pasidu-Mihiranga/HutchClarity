# Hutch Clarity - Rule Engine, Decision Policy & Trust Receipts

[← 08-ai-architecture.md](08-ai-architecture.md) · [← Plan index](README.md) · [10-data-api-events.md →](10-data-api-events.md)

> Part of the **Hutch Clarity Enterprise Project Plan**. Labels: `[DECK Sx]` = stated in deck slide x · `[PROPOSED]` = expanded by this plan · **ASSUMPTION** / **REQUIRES HUTCH CONFIRMATION** / **PROPOSED TARGET – REQUIRES HUTCH VALIDATION**. See the [index](README.md) for the full legend.

> **Plan v1.1 (2026-10-01).** Updated to match [17](17-build-blueprint.md), [18](18-tech-stack-and-ai.md) and [19](19-policy-change-management.md). Change record: [CHANGES.md](CHANGES.md).

## 13. Rule Engine

### 13.1 Concept (v1.1)
A "rule" is three versioned artefacts that are released together as one **signed rule bundle**:

| Part | Form | Who edits | Why this form |
|---|---|---|---|
| **Manifest** | YAML: identity, owner, legal basis, required evidence, parameters, ruled-out list, allowed actions, templates, tests | CX engineer | Human-readable metadata and parameters |
| **Detector** | Python plugin `clarity.detectors.<rule>:detect`, versioned with the manifest | Engineer | Temporal evidence logic is clearer, typed and testable in code than in a home-made DSL |
| **Parameters** | Values in the config store with scoped, effective-dated overrides ([19](19-policy-change-management.md)) | CX engineer, approved by finance/compliance | Thresholds change often; they must not need a code release |

- Every decision records `rule_id@version`, `bundle_hash` and the resolved `config_snapshot_hash` `[DECK S7]`.
- Parameter and decision-table changes need no code deploy (four-eyes publish). Detector logic changes go through PR review + golden tests + shadow evaluation `[DECK S7, S14]`.
- The lifecycle for all of these is defined once in [19](19-policy-change-management.md).

### 13.2 Rule manifest and detector (illustrative)

```yaml
rule_id: VAS_NO_CONSENT
version: 4
status: active                      # draft | in_review | approved | scheduled | active | superseded | retired
owner: vas-ops
legal_basis: "Gazette 2316/14 - VAS requires consent + OTP"
applies_to: { domain: prepaid, event_types: [vas_charge] }
detector: clarity.detectors.vas_no_consent:detect     # Python plugin, same version
required_evidence: [charging, vas_consent]            # missing -> evidence incomplete -> handoff, never a guess
params:                                               # defaults; overridden by scoped config (see ch. 19)
  consent_lookback: P400D
  base_confidence: 0.90
  high_risk_merchant_boost: 0.05
  partial_consent_source_penalty: 0.30
rules_out: [PACK_EXPIRY_BURN, LOAN_RECOVERY]
allowed_actions: [REFUND, DEACTIVATE_VAS, BLOCK_MERCHANT_UNTIL_OPTIN]
safeguard: BLOCK_MERCHANT_UNTIL_OPTIN
recurrence_check: merchant_block_active
explanation_template_ids: { si: vas_no_consent_si_v3, ta: vas_no_consent_ta_v3, en: vas_no_consent_en_v3 }
decision_table: clarity.decision.vas                  # thresholds live in the ZEN table, not here
tests_ref: rules/golden/VAS_NO_CONSENT/v4/
```

```python
# rules/detectors/vas_no_consent.py  (sketch)
def detect(tl: TimelineSnapshot, p: Params) -> list[CauseFinding]:
    findings = []
    for c in tl.events("vas_charge"):
        otp = tl.last("consent_otp_verified", subscription_id=c.subscription_id,
                      before=c.at, lookback=p.consent_lookback)
        second = tl.last("second_confirmation", subscription_id=c.subscription_id, before=c.at)
        if otp is None and second is None:
            conf = p.base_confidence
            conf += p.high_risk_merchant_boost if tl.merchant_risk(c.merchant_id) == "high" else 0
            conf -= p.partial_consent_source_penalty if tl.completeness("vas_consent") == "partial" else 0
            findings.append(CauseFinding("VAS_NO_CONSENT", confidence=conf,
                                         money_effect=c.amount, evidence=[c.ref, tl.absence_ref("vas_consent")]))
    return findings
```

Detectors are pure functions of `(snapshot, params)`. They have no I/O and no clock, so every result can be replayed exactly.

### 13.3 Candidate rule catalogue (16)
**Inferred from deck causes - final list REQUIRES HUTCH product/CX confirmation.**

| # | Rule ID | Cause | Typical outcome | Deck basis |
|---|---|---|---|---|
| 1 | VAS_NO_CONSENT | VAS charge with no OTP / second confirmation | One-tap fix | S6, S7 |
| 2 | VAS_RENEWAL_UNNOTIFIED | Renewal without required prior notice (**policy to confirm**) | One-tap fix / explain | S6 "early VAS renewal" |
| 3 | DUPLICATE_RELOAD | Two captures, one credit | Auto-fix | S2, S5 |
| 4 | RELOAD_NOT_CREDITED | Capture with no balance credit | Auto-fix if small, else staff | S2, S11 |
| 5 | PAYMENT_PENDING_SETTLEMENT | Bank pending; not yet failed | Explain only + watch | `[PROPOSED]` |
| 6 | PACK_EXPIRY_BURN | Data on main balance after pack end | Explain + safeguard offer | S6, S7 |
| 7 | FUP_CAP_REACHED | Throttled after disclosed FUP | Explain only | S2, S7 |
| 8 | FUP_NOT_DISCLOSED | Cap applied but not shown at purchase (catalogue version) | Staff / one-tap remedy | S5 pack truth label |
| 9 | PACK_MISMATCH | Sold pack ≠ provisioned pack | One-tap fix + product alert | S10, S11 |
| 10 | SOCIAL_PACK_SCOPE | App traffic outside social-pack scope | Explain only | S11 |
| 11 | PACK_SUNSET | Retired pack auto-migrated | Explain + migration card | S11 |
| 12 | LOAN_RECOVERY | Emergency credit recovered from reload | Explain only | S7 |
| 13 | BALANCE_BURN_PAYG | Pay-as-you-go usage with no pack | Explain + safeguard | S11 |
| 14 | WRONG_PACK_PURCHASE | Customer bought the wrong pack (even if used) | One-tap fix within policy window | S7 |
| 15 | DUPLICATE_VAS_CHARGE | Same subscription charged twice in a period | Auto-fix | `[PROPOSED]` |
| 16 | OUTAGE_DURING_PACK | Network outage consumed pack validity | Staff / goodwill per policy | S6, S10 |

### 13.4 Rule lifecycle (teach once → publish) - Diagram 23

```mermaid
flowchart LR
    A["Agent correction<br/>Teach once"] --> B["Golden case created"]
    AU["Autopsy new cluster"] --> C["Rule proposal draft"]
    B --> C
    C --> D["CX engineer edits detector, params or table"]
    D --> E["Golden tests<br/>positive · negative · boundary"]
    E --> F["Replay on historic cases<br/>policy what-if"]
    F --> G{"Deltas acceptable?"}
    G -- no --> D
    G -- yes --> H["Four-eyes approval<br/>CX + finance or VAS + compliance"]
    H --> I["Sign + publish version N+1"]
    I --> J["Shadow evaluate vs N"]
    J --> K["Activate by flag / cohort"]
    K --> L["Monitor overrides + false positives"]
    L --> D
```

### 13.5 Golden tests (every RuleVersion)

| Test type | Example for VAS_NO_CONSENT v4 |
|---|---|
| Positive | Charge LKR 49, no OTP event → match, confidence ≥ 0.90 |
| Negative | Charge with OTP verified 3 days earlier → no match; listed under "ruled out" |
| Boundary | OTP at exactly lookback limit; OTP 1 s after charge; partial consent-source completeness → confidence penalty → staff |
| Replay | Re-run 1,000 anonymized historic cases: v4 vs v3 outcome diff must equal the approved delta list |
| Property-based | Hypothesis-generated timelines: the rule never matches when `consent_otp_verified` precedes the charge |

Coverage gate: every condition branch is exercised (NFR-MNT-01). Replay snapshots are stored with their evidence hash so any historic decision can be reproduced bit-for-bit `[DECK S14]`.

---

## 14. Decision Policy

### 14.1 Inputs
Confidence of the top cause · margin to the second cause (conflict) · amount vs caps · evidence completeness · risk (SIM swap within N days, fraud flags, repeat-refund history) · action reversibility · customer request for a human · daily refund budget remaining · channel (the SMS/USSD channel supports only explain + simple confirm).

### 14.2 Outcome matrix (expands `[DECK S7]`)
All thresholds are **PROPOSED TARGET – REQUIRES HUTCH VALIDATION** (Finance/CX/Risk owners), configurable `[DECK S7]`. They are parameters in the config store; changing them follows [19](19-policy-change-management.md).

| Outcome | Conditions (all must hold) | Example |
|---|---|---|
| **Auto Fix** | Money back only (no service change) · confidence ≥ 0.95 · amount ≤ auto cap (e.g., LKR 1,000) · evidence complete · no SIM swap ≤ 7 days · no fraud flag · margin ≥ 0.20 · budget available · rule whitelisted for auto | Double reload refunded unasked `[DECK S5, S7]` |
| **Fix with Confirmation** (one tap) | Confidence ≥ 0.90 · amount ≤ one-tap cap (e.g., LKR 5,000) · a service change is involved **or** the rule isn't auto-whitelisted · evidence complete · no risk flags | VAS without OTP; wrong pack `[DECK S7]` |
| **Staff Approval** | Above cap · recent SIM swap · fraud flag · two causes within margin · confidence 0.70–0.90 · reversibility low | Large disputed reload `[DECK S7]` |
| **Explain Only** | Top cause is a rule the customer saw (disclosed) · no money owed | "Unlimited" hit a disclosed FUP `[DECK S7]` |
| **Human Handoff** | Required log missing · fraud risk high · confidence < 0.70 · customer asks · verifier fails twice | Staff start with the full trail `[DECK S7]` |

Additional tiers: above a finance threshold (e.g., LKR 25,000, **ASSUMPTION**), four-eyes (supervisor + finance). The daily refund budget is enforced per rule and globally; when exhausted, auto/one-tap degrade to staff approval. Daily reconciliation compares actions against adapter confirmations `[DECK S7]`.

### 14.3 Decision table sketch (GoRules ZEN, illustrative)

The outcome matrix is a **ZEN decision table** (JSON Decision Model), editable in the Policy Studio, hit policy *first*. OPA/Rego is kept for **authorization** (who may approve, MCP access), not for outcomes.

| # | evidence_complete | risk_flag | confidence | margin | amount ≤ | money_back_only | rule in auto whitelist | budget ok | → outcome |
|---|---|---|---|---|---|---|---|---|---|
| 1 | false | – | – | – | – | – | – | – | HANDOFF |
| 2 | – | high fraud | – | – | – | – | – | – | HANDOFF |
| 3 | true | none | ≥ `auto.confidence` | ≥ `conflict_margin` | `auto.cap_lkr` | true | true | true | AUTO_FIX |
| 4 | true | none | ≥ `one_tap.confidence` | ≥ `conflict_margin` | `one_tap.cap_lkr` | – | – | true | ONE_TAP_FIX |
| 5 | true | – | 0.70–0.90 or margin < `conflict_margin` or above cap or SIM swap | | | | | | STAFF_APPROVAL |
| 6 | true | – | – | – | – | – | – | – | per rule: EXPLAIN_ONLY if `disclosed`, else HANDOFF |

Cells in `backticks` are **parameters** resolved from the config store at `as_of = event time` ([19](19-policy-change-management.md)). Every evaluation stores the decision-table version, the config snapshot hash and the full input hash in `Decision`. That makes Policy what-if `[DECK S9]` an exact replay with a candidate table or parameter set.

---

## 15. Trust Receipt Architecture

### 15.1 Receipt schema (canonical JSON, signed)

```json
{
  "receipt_id": "TR-2027-000184",
  "schema_version": "1.0",
  "case_id": "CASE-01J...",
  "issued_at": "2027-09-14T08:42:10Z",
  "subject": { "msisdn_masked": "07X XXX 4567", "subscriber_ref_hash": "sha256:..." },
  "what_happened": { "cause_rule": "VAS_NO_CONSENT", "rule_version": 4, "summary_fact_ids": ["f1","f2"] },
  "evidence": [ { "event_id": "ev-...", "source": "charging", "hash": "sha256:..." },
                { "event_id": "ev-...", "source": "vas_consent", "assertion": "no_otp_found", "hash": "sha256:..." } ],
  "decision": { "decision_id": "DEC-...", "outcome": "ONE_TAP_FIX", "policy_version": "2027.09.1" },
  "actions": [ { "action_id": "ACT-...", "type": "REFUND", "amount_lkr": "49.00",
                 "before": { "balance_lkr": "263.00" }, "after": { "balance_lkr": "312.00" },
                 "status": "COMPLETED", "adapter_ref": "..." } ],
  "safeguard": { "type": "BLOCK_MERCHANT_UNTIL_OPTIN", "status": "ACTIVE" },
  "recurrence_test": { "check": "merchant_block_active", "result": "PASSED", "checked_at": "..." },
  "actor": { "type": "customer_confirmed", "approver_role": null, "system": "clarity-tool-layer@1.8.2" },
  "languages": ["si","ta","en"],
  "prev_receipt_hash": "sha256:...",
  "payload_hash": "sha256:...",
  "signature": { "alg": "Ed25519", "kid": "clarity-rcpt-2027-01", "value": "base64..." },
  "verify_url": "https://<hutch-domain>/v/TR-2027-000184"
}
```

### 15.2 Design decisions

| Element | Decision |
|---|---|
| Receipt ID | Human-quotable `TR-YYYY-NNNNNN` `[DECK S6]` + internal ULID. The sequence is allocated per year. |
| Canonicalization | RFC 8785 JSON Canonicalization Scheme before hashing |
| Hash chain | `payload_hash = SHA-256(JCS(payload_without_sig) ‖ prev_receipt_hash)`, serialized per partition (e.g., per day/shard) with row locks to avoid contention. Chain head anchored to WORM storage and the SIEM every N minutes. |
| Signature | Ed25519 `[DECK S6]` over `payload_hash`. Keys in HSM/KMS; `kid` in receipt; public keys at `/.well-known/clarity-keys.json`; annual rotation (**ASSUMPTION**), old keys kept for verification. |
| QR | Encodes `verify_url` + short signature fingerprint. No PII in the QR. |
| Public verification page | Shows VALID/INVALID, issue date, masked number, amounts corrected, safeguard status. Full evidence only for an authenticated owner or staff. |
| Audit record | Each issuance writes an `AuditEvent(receipt.issued)` linked to the decision/action audit chain |
| Replay | `POST /receipts/{id}/replay` (staff/auditor) re-runs the rule + policy versions on the evidence snapshot and must reproduce the decision |
| Formats | PNG, PDF, SMS (short form with ID + URL), in si/ta/en `[DECK S6]` |
| Revocation / correction | Receipts are never edited. A correction issues a new receipt that references `supersedes`. The verify page shows "superseded by …". |
| Fake receipt defence | Only signed receipts in the ledger verify. Forged PDFs fail the signature/lookup. Customer/agent verification counts are monitored, and a spike in failed verifications raises an alert ([§19](11-security-privacy-audit.md) threat model). |

Generation and verification sequence: **Diagram 14**.
---

[← 08-ai-architecture.md](08-ai-architecture.md) · [← Plan index](README.md) · [10-data-api-events.md →](10-data-api-events.md)

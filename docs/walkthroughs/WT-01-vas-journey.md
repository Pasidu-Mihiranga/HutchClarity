# WT-01 - VAS silent renewal journey

| Field | Value |
|---|---|
| Audience | developers / demo presenters / judges |
| Journey | Customer asks "Why was I charged?" for a VAS renewal without recent OTP |
| Status | draft |
| Last verified | 2026-10-02 |

## 1. What you will see

Dilani opens Why? after a GameHub daily subscription renews for LKR 49 without
a fresh OTP. Clarity shows the cause with evidence, proposes cancel + credit
(or refund by rule), she confirms in one tap, and receives a signed Trust
Receipt.

## 2. Prerequisites

```bash
make up-lite
make seed          # if wired against DATABASE_URL
make dev-new       # modular monolith API, or `make dev` for legacy UI
```

Demo subscriber (synthetic): MSISDN `0771234567` / scenario VAS silent renewal.

## 3. Steps

| # | You do | UI / channel | API call | Module(s) | What to check |
|---|---|---|---|---|---|
| 1 | Open customer Why? | web `/` | `POST /v1/cases` | case, conversation | case created for Dilani |
| 2 | Evaluate | Why? screen | `POST /v1/cases/{id}/evaluate` | timeline, detection, decision | cause `vas_silent_renewal`, evidence listed |
| 3 | Propose fix | Confirm CTA | `POST /v1/actions/propose` (idempotency key) | actions | proposal pending |
| 4 | Confirm | One tap | `POST /v1/actions/confirm` + execute | actions | action completed; no LLM authority |
| 5 | Receipt | Receipt page | `GET` receipt / verify | receipts | Ed25519 verify OK |

## 4. Under the hood

- Detectors: `vas_silent_renewal` (and related VAS rules).
- Outbox event: `action.completed` → receipts consumer.
- MCP path (optional): `propose_action` with Bearer + `idempotency_key` only;
  never execute.

## 5. Variations and failure paths

- Missing OTP evidence → handoff, not auto-credit.
- Budget exhausted → 429 / desk queue.
- LLM disabled → CX template explanation still works.

## 6. Troubleshooting

- Empty world: run seed / `POST /v1/demo/reset` on the legacy app.
- Auth on MCP: send `Authorization: Bearer dev-token`.

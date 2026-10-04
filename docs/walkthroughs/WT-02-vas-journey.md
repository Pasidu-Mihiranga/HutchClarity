# WT-01 - VAS silent renewal journey

> **Merged 2026-10-02:** imported from the team's `main` into the `dev` branch; paths updated to the R1 layout (see `2026-10-02-R1-dev-merge.md`).

| Field | Value |
|---|---|
| Audience | developers / demo presenters / judges |
| Journey | Customer asks (chip or free-form) about an unexpected VAS charge; Clarity Investigation Card → confirm modal → refund → Trust Receipt |
| Status | verified, API path and browser steps |
| Last verified | 2026-10-04 (browser suite and live VPS release `01d1762`: trusted HTTPS, synthetic OTP, evidence, LKR 49 action and persisted verified receipt) |

> **FE01 (#28), 2026-10-04.** Both halves are now verified. The acceptance
> suite drives this flow over `/v1` and ends at a receipt the backend verifies
> (`test_the_dispute_charge_script_for_dilani_ends_with_a_verified_receipt` and
> `tests/acceptance/test_assistant.py`), and the browser steps below are driven
> by `frontend/e2e/dispute-charge.spec.ts`, which ran green for the first time
> in this change (14 of 14 in the suite). C05 wrote that suite but could not
> execute it, so until now the steps below were only "believed correct".
>
> What C05 changed in the browser path: the chat now sends `case_id` at the top
> level of the turn request, so the server-side flow actually runs. Before C05
> it was sent only inside `facts` and every turn took the stateless path, which
> means the "progress trail" step below was driven entirely client side.

## 1. What you will see

Dilani opens **Clarity** (full-page chat). Welcome shows large suggestion
cards; a personalized chip may already show **Why was LKR 49 deducted?**
(or she types free-form / Sinhala). Clarity shows a short progress trail,
then an **Investigation Card** with evidence, finding, and **Refund & Disable**.
Confirm opens a consequence modal. After confirm she gets **Success** plus an
in-thread **Trust Receipt** card and follow-up chips (prevent / support).

## 2. Prerequisites

```bash
make dev           # API on :8000
make web-install   # once
make web           # the three Next.js apps: :3000 customer, :3001 console, :3002 verify
```

Open the customer app at <http://localhost:3000>. FE01 retired the static UI
the API used to serve, so `make dev` on its own gives you the API and no
pages.

Demo subscriber (synthetic): MSISDN `0781234567` (Dilani) / VAS silent renewal.

## 3. Steps

| # | You do | UI / channel | API call | Module(s) | What to check |
|---|---|---|---|---|---|
| 1 | Sign in as Dilani, open Clarity | immersive chat | `GET /v1/me/app` | iam, customer | Welcome + suggestion cards via `POST /v1/conversation/suggestions` |
| 2 | Tap card **or** type "Why was Rs 49 deducted?" / Sinhala | Clarity chat | `POST /v1/conversation/turn` | conversation | Intent `UNEXPECTED_CHARGE` or `BALANCE_*`, route `account`; thinking + progress steps |
| 3 | Wait for Investigation Card | transcript | `POST /v1/cases` + `.../evaluate` | case, detection, decision | Evidence checklist + finding + Refund & Disable CTA |
| 4 | Confirm in modal | Confirm Disable modal | proposals + confirm / auto-fix | actions | Money moved only by tool layer after Confirm |
| 5 | View Trust Receipt | Success + TrustReceipt cards | receipt verify | receipts | Ed25519 verify OK; follow-ups shown; New chat resets welcome |

## 4. Under the hood

- Suggestions are **shortcuts**, not FAQ answers; free-form uses the same turn → evaluate path.
- Detectors: VAS silent renewal / no-consent family.
- Follow-ups re-enter `ask()` with chat intent + prior `facts` (`case_id`, `product`, `amount_lkr`).
- Chat history is demo-scale `localStorage` only (New chat / History in the header).

## 5. Variations and failure paths

- Missing OTP evidence → handoff / EXPLAIN_ONLY, not auto-credit.
- Knowledge questions (eSIM) → KnowledgeAnswer card, no money path.
- "Talk to support" → HumanHandoffCard.

## 6. Troubleshooting

- Empty cards: hard-refresh; suggestions fall back to defaults if the API errors.
- Empty world: `POST /v1/demo/reset` against the API, or **Reset demo data**
  on the console's Desk.

# receipts - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.receipts`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `openbao.py`, `public.py`, `recurrence.py`, `render.py`, `render_job.py`, `repository.py`, `service.py`, `signing.py` |

## 1. Purpose
Trust Receipts: build the canonical payload, chain to the previous receipt, sign with Ed25519, verify (hash, signature, ledger, chain), run the recurrence test, render PNG/PDF/SMS in si/ta/en.

## 2. Public surface (`public.py`)
Other code imports only `public.py`, including the signer port, dev/OpenBao drivers, receipt service and renderer.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`, `clarity.modules.case`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.kernel` | - |
| `clarity.modules.actions` | public |

## 5. Data owned
The hash-chained receipt ledger in issue order, what each receipt supersedes, which subscriber each is about, and the receipt-number sequence, behind `ReceiptRepository` (B02). Collections: `receipts.chain`, `receipts.superseded`, `receipts.subscriber`, `receipts.sequence`, `receipts.by_plan` (one plan, one receipt: the index that makes issuance idempotent, B06). Order is part of the data: the repository preserves issue order, which is what the chain walk relies on. The `demo` profile binds the in-memory driver, `full` binds PostgreSQL schema `receipts` with its own role (ADR-0013); both pass `tests/contract/test_repository_parity.py`.

## 6. Invariants
- Receipts are never edited; a correction supersedes.
- A recurrence test passes only when live state proves the safeguard; an unavailable probe reports UNAVAILABLE.
- Evidence is cited by id and hash, never copied.

## 7. Migration status (enterprise-plan 21)
M-RCPT complete: lite uses a rotatable dev Ed25519 key; full can use the OpenBao Transit/KMS driver and publishes all retained public keys. Rendering is a stateless job with browser networking blocked. Receipt state and `receipt.issued@v1` are committed together.

## 8. Tests
- `tests/contract/test_port_parity.py`
- `tests/unit/test_receipts.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.receipts` with a public surface (R1) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-B02-unit-of-work-and-repositories.md` | The receipt chain, supersession map, subscriber map and sequence moved behind `ReceiptRepository` (B02, #5) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-B06-receipts-on-action-completed.md` | `issue(plan_id=...)` is idempotent per plan via a plan index; `for_plan()` added (B06, #14) |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-M-RCPT-openbao-and-render-isolation.md` | OpenBao signer, rotation and isolated render job (M-RCPT, #37) |

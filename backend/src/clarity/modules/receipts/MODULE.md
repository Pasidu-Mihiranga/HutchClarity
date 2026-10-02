# receipts - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.receipts`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `public.py`, `recurrence.py`, `render.py`, `service.py`, `signing.py` |

## 1. Purpose
Trust Receipts: build the canonical payload, chain to the previous receipt, sign with Ed25519, verify (hash, signature, ledger, chain), run the recurrence test, render PNG/PDF/SMS in si/ta/en.

## 2. Public surface (`public.py`)
Other code imports only these names: `DevSigningService`, `ReceiptService`, `RenderFormat`, `RendererUnavailable`, `SigningService`, `UnknownKeyId`, `render`.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`, `clarity.modules.case`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.kernel` | - |
| `clarity.modules.actions` | public |

## 5. Data owned
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `receipts` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- Receipts are never edited; a correction supersedes.
- A recurrence test passes only when live state proves the safeguard; an unavailable probe reports UNAVAILABLE.
- Evidence is cited by id and hash, never copied.

## 7. Migration status (enterprise-plan 21)
Signing key generated in memory (`lite`). R4: `clarity-signer` with OpenBao/KMS. R3: one receipt per completed plan, issued by an idempotent consumer.

## 8. Tests
- `tests/contract/test_port_parity.py`
- `tests/unit/test_receipts.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.receipts` with a public surface (R1) |

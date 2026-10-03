# deskops - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.deskops`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` and `full`): bulk fix, merchant watch, regulator pack and shift handover, D01 (#26), 2026-10-04 |
| Files | `bulk.py`, `watch.py`, `service.py`, `public.py` |

## 1. Purpose

What a CX desk does across many cases at once: a bulk fix with a dry run and
four-eyes, merchant watch scores, a regulator pack and a shift handover
(plan 02 section 3.5).

A bulk fix is the most dangerous feature in the product. One operator deciding
that forty cases share a cause and fixing them in one action is what the deck
promises, and it is one mistake away from forty wrong refunds, so most of this
module is refusals.

## 2. Public surface (`public.py`)

Bulk fix: `DeskOps`, `BulkFixes`, `BulkFix`, `DryRun`, `CasePreview`,
`CaseResult`, `BatchApproval`, `BatchStatus`, `Eligibility`, `CaseFixer`,
`BulkFixRefused`, `BATCHES`.

Desk views: `DeskCase`, `DeskCases`, `MerchantScore`, `RegulatorPack`,
`Handover`, `merchant_watch`, `regulator_pack`, `handover`, `WEIGHTS`,
`DEFAULT_WINDOW`.

## 3. Used by

`clarity.app.container`, which constructs `DeskOps` with the two adapters in
`clarity.app.desk`.

## 4. Depends on

| Package | Through |
|---|---|
| `clarity.kernel.canonical` | `hash_payload`, for the dry-run fingerprint |
| `clarity.kernel.common` / `ids` | `utc_now`, `new_id` |
| `clarity.platform.persistence` | `Repository`, `UnitOfWork`, `UnitOfWorkFactory`, `MemoryStore` |

No synchronous call to another module (`"deskops": set()` in
`tests/architecture/test_module_dependencies.py`). Cases are reached through
the `CaseFixer` and `DeskCases` protocols the composition root fills, the same
arrangement C02 used for the flow tools and AU01 for the complaint source.

## 5. Data owned

`deskops.batches`: one record per bulk fix, with its dry run, approvals and
per-case results. One PostgreSQL schema and role in the `full` profile,
in-memory in `lite`.

Stored because an approval is worthless if it dies with the request that
recorded it, and because the per-case results are the record of a money
movement that somebody authorised.

## 6. Invariants

- **A bulk fix executes each case's own existing plan and cannot invent one.**
  The desk chooses *which cases*, never *what to do to them*: what may happen
  to a case was settled by its decision under the policy resolved as of its
  event (I1, D2).
- **The approval is of a specific dry run, not of a batch id.** The dry run is
  fingerprinted over the eligible cases, their plan ids and their amounts; the
  approval carries that fingerprint; and execution refuses a different one.
  Without this, four-eyes approves a label and a checker who approved forty
  cases can find eighty executed.
- **Maker is never checker**, at the batch level and again per case. The batch
  gate is D01's; the per-case gate is the tool layer's existing
  `approve_by_staff` refusal and still applies, so a bulk fix cannot be used
  to get around it.
- **`ONE_TAP_FIX` is never bulk executed.** A one-tap fix is the customer's
  tap and executing it for them needs a token minted from that tap
  (ADR-0007). Only `AUTO_FIX` and `STAFF_APPROVAL` are actionable.
- **A partial failure is reported, never rolled back.** Refunds that succeeded
  are customers who have their money; unwinding them to make a batch look
  atomic would be a second unauthorised movement.
- **Re-executing a batch does nothing further** (I8).
- **A batch bigger than a person can read is refused.** 200 cases. Not a
  performance limit: a batch nobody can review before approving is a batch
  nobody approved.
- **A batch needs a reason.** It is what the checker approves and what the
  audit trail will be asked about.
- **Every desk figure is counted, never modelled**, and a merchant score
  carries what it was counted from so a reader can argue with the weighting
  rather than with the number.
- **The regulator pack carries no personal data.** Every subscriber is an HMAC
  reference; there is no MSISDN, no name and no customer text (I13).
- Time comes from the injected clock (I11).

## 7. Migration status (enterprise-plan 21)

R6/R7. The bulk fix, the three views and the persistence are in place.

**Not yet:** a `/v1` surface, so the desk is reachable from code and tests
only; the console does not render any of it; and `WEIGHTS` is a module
constant that nothing has tuned, marked
**PROPOSED TARGET - REQUIRES HUTCH VALIDATION**.

A bulk fix is not published through `PolicyGovernance`. It is not a policy
change, so that is arguably right, but a remediation across hundreds of
customers is the kind of thing plan 20's change classes exist for and the
question is worth asking before this reaches production.

## 8. Events

None produced or consumed. A bulk fix's per-case executions produce
`action.completed` through the tool layer as any single fix does, and the
receipts follow from those, so the batch itself needs no event of its own.

A `deskops.batch.executed` event would be the natural way for insights and
audit to see a remediation as one thing rather than N unrelated fixes. Not
declared, because nothing consumes it yet (the same reasoning K01 used).

## 9. Tests

- `backend/tests/unit/test_deskops.py` - four-eyes at both levels (D01
  acceptance 1), the dry-run fingerprint, what a batch may and may not do, the
  three views, and the whole thing against the real container with the
  assertions on balances and receipts

## 10. Change history

| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-dev-merge.md` | Scaffold: `public.py` and `MODULE.md` stubs to satisfy the architecture tests |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-D01-desk-operations.md` | Bulk fix with a dry run and four-eyes, merchant watch, regulator pack and shift handover |

# 2026-10-04 - D01 - Desk operations, and the check that makes four-eyes mean anything

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | D01 (`docs/backlog/issues/D01-desk-operations-bulk-fix-with-four-eyes-merchant.md`, #26), Wave 4 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.deskops` (`bulk.py`, `watch.py`, `service.py`, `public.py`), `app` (`desk.py` new, `container`, `collections`) |

## What changed

`deskops` was a scaffold. It now has:

- **`bulk.py`**: a batch from dry run to receipts, and the refusals.
- **`watch.py`**: merchant watch scores, the regulator pack and the shift
  handover, all counted reads.
- **`service.py`**: `DeskOps`, holding batches so an approval survives.
- **`app/desk.py`**: the two adapters joining the desk to the case service.

## The check the issue does not ask for, and the one that matters

Acceptance 1 is "a bulk fix by its maker alone is refused". That is the obvious
gate and it was quick: refuse an approver who is the maker, and refuse an
execute with no approval. Both are tested, and both by the real container with
assertions on the balance rather than on an exception, because a refusal that
raised after the refund went out would satisfy `pytest.raises` and fail the
customer.

The check that makes those mean anything is different. **A checker who
approves "refund these 40 cases" and finds 80 executed has not approved what
happened.** Four-eyes over a batch id approves a label.

So a dry run is fingerprinted over exactly what it said would happen, the
eligible cases with their plan ids and their amounts; the approval carries that
fingerprint; and execution re-runs the dry run and refuses if it has moved. The
test that proves it is the one where a third case becomes eligible between
approval and execution: without the check, that case is refunded by an approval
nobody gave it.

The fingerprint covers the **amount** as well as the case, because approving
"refund 49 each" and executing 4900 each is the same case list and a different
thing entirely. It ignores case order, because an approval that broke when an
unordered read came back differently would be worse than no approval at all.

## A bulk fix cannot invent an action

The desk chooses *which cases*, never *what to do to them*. What may happen to
a case was settled by its decision, under the policy resolved as of its event
(I1, D2), so a batch executes each case's own existing pending plan and nothing
else. A case with no plan is skipped, and the desk cannot propose one in bulk.

That is also why the fixer is the **ordinary single-case path**. The adapter
calls `approve_and_execute` or `auto_fix`, which mint the confirmation token,
apply the tool layer's own four-eyes and idempotency, and issue the one receipt
that plan produces. A bulk fix is therefore N ordinary fixes: it cannot reach
anything an operator could not do one case at a time, and it does not get its
own execution code to go wrong differently.

## The correction that cost a test run

The first version of the adapter treated `ONE_TAP_FIX` as actionable. Every
case came back refused:

```
ApprovalRequired: a ONE_TAP_FIX decision is not a staff approval
```

The tool layer was right and I was wrong. **A one-tap fix is the customer's
tap**, and executing it for them needs a confirmation token minted from that
tap (ADR-0007). A desk cannot mint one, and a desk that could would be deciding
on a customer's behalf in a case whose policy said to ask them.

So only `AUTO_FIX` (already whitelisted for zero contact) and `STAFF_APPROVAL`
(staff work by definition) are actionable. Remediating a population of one-tap
cases means either getting those customers to tap or changing the policy that
classified them, and both are decisions somebody has to make rather than a
desk batch to run. `test_a_one_tap_case_is_never_bulk_executed` records it,
because the mistake is an easy one to make again.

The routing follows from it: `AUTO_FIX` goes through `auto_fix` attributed to
the batch's approver rather than to the stream detector that usually triggers
one, and `STAFF_APPROVAL` through `approve_and_execute` so the per-case
four-eyes applies as well as the batch's.

## Two more refusals worth the words

**A partial failure is reported, never rolled back.** Twelve refunds that
succeeded are twelve customers who have their money. Unwinding them to make a
batch look atomic would be a second unauthorised movement, so the batch reports
per case and the successes stand. One test executes a batch where one case
fails and asserts the other's receipt exists and the failure produced none.

**A batch over 200 cases is refused**, and not for performance. A checker
scrolling 5000 rows is rubber stamping, so a batch nobody can read before
approving is a batch nobody approved. A bigger remediation is several reviewed
batches, which is slower on purpose.

## The three read-only views

Merchant watch, the regulator pack and the handover are counted reads over case
records. Three decisions:

1. **Every figure is counted, never modelled.** A watch score that blended a
   count with a trend estimate would be a prediction wearing a count's clothes
   and the desk would act on it.
2. **A score carries what it was counted from.** The weighting is a judgement,
   so a reader has to be able to disagree with the weighting rather than with
   the number. `WEIGHTS` is a stated table and is
   **PROPOSED TARGET - REQUIRES HUTCH VALIDATION**: nothing has tuned it.
3. **The regulator pack carries no personal data.** Every subscriber is an HMAC
   reference; there is no MSISDN, no name and no customer text (I13). A
   regulator asking "what did you do about unconsented charging" needs counts,
   causes and receipt ids, and a pack that carried identities would be a
   personal data export with a different name. A test greps the rendered pack
   for phone-number shapes.

A smaller one: `_moved` sums the **executed actions'** amounts rather than the
plan's total. A partially compensated execution moved less than its plan said,
and a desk view showing the plan's figure would overstate the remediation.

And the handover leads with what is outstanding rather than what happened most
recently, so the next shift can start on the oldest thing still waiting. A test
asserts the pack and the handover count one window the same way, because two
desk views disagreeing is a desk that trusts neither.

## Contract and plan notes

- **No `/v1` change and no snapshot change.** There is no desk route yet, which
  is the largest gap below.
- **No new module edge.** `"deskops": set()` holds: cases are reached through
  the `CaseFixer` and `DeskCases` protocols the composition root fills, the
  same arrangement C02 used for flow tools and AU01 for the complaint source.
- **No new event.** The per-case executions already produce `action.completed`
  through the tool layer, so the batch needs none of its own. A
  `deskops.batch.executed` would let insights and audit see a remediation as
  one thing rather than N unrelated fixes, and is not declared because nothing
  consumes it (the reasoning K01 used).
- Collection `deskops.batches` registered.

## Docs updated

- This devlog, `backend/src/clarity/modules/deskops/MODULE.md` (replacing the
  scaffold stub), `CHANGELOG.md`, `ARCHITECTURE.md`, `docs/modules.md`,
  `plan.md` (#26 ticked).
- No `.env.example` change.

## Tests run

- `make check`: **1727 passed, 544 skipped** (1694 before D01).
- `backend/tests/unit/test_deskops.py`, 33 tests.
- Acceptance 1 by both routes and at both levels: the maker cannot approve
  their own batch, and a batch with no approval cannot execute. Asserted
  against the real container on the balance and the receipt chain.
- The dry-run fingerprint: a wrong fingerprint is refused, a batch that grew
  after approval will not execute, the fingerprint covers the amount and
  ignores case order.
- The real container: a dry run moves nothing and says which cases it would
  skip, an approved batch pays out once per case with distinct receipts,
  re-executing pays out nothing further, a one-tap case is never executed, and
  the previewed amount equals the plan's.
- Non-vacuity, two probes: removing both four-eyes gates fails the two
  acceptance tests and the real-container money assertion; removing the
  approval-drift check fails the batch-that-grew test.

## Known gaps

- **No `/v1` surface.** The desk is reachable from code and tests only, so the
  permissions that exist for it (`MERCHANT_SUSPEND`,
  `REGULATOR_PACK_EXPORT`, `DESK_QUEUE_READ`) are not yet enforced on any
  route. That is the next thing to build and it is deliberately not smuggled
  in here: a money-path route wants its own review (CODEOWNERS asks for two
  approvals on `modules/actions`, and a route that drives bulk execution is in
  the same category).
- **The console does not render any of it.**
- **A bulk fix is not published through `PolicyGovernance`.** It is not a
  policy change so that is arguably right, but a remediation across hundreds
  of customers is the kind of thing plan 20's change classes exist for, and
  the question is worth settling before this reaches production.
- `WEIGHTS` and the 200-case limit are module constants that nothing has tuned
  on anything.
- Merchant watch reads `merchant_id` from timeline attributes, so a merchant
  that appears only in an adapter that does not set that attribute is invisible
  to the watch. That is an adapter mapping concern (plan section 9.1) and worth
  a check when a real adapter lands.

## Next step

Wave 4's remaining items. The cross-cutting gaps are unchanged and now span
more work packages: an embedding model (K02, K03, AU01), a recorded cassette so
any model path is exercised at all (C03, C04, K03), publishing content
artefacts through `PolicyGovernance` (C02, K01, AU01), and `/v1` surfaces for
the two modules built this session without one (AU01, D01).

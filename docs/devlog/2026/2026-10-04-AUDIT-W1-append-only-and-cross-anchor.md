# 2026-10-04 - AUDIT W1 and Phase 2 - append-only in the database, and receipts as witnesses

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Opus), for Thanoj Buddhima |
| Work package | Audit assurance plan, the last two open items |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | platform.persistence, platform.audit, contracts.receipt, modules.receipts, app.container, interfaces.http, contracts, CI |

## What changed

**W1, database-level append-only.** `APPEND_ONLY` in `persistence.schemas` names
the three audit collections. Both drivers honour it: PostgreSQL plainly inserts
instead of upserting, the memory store refuses an overwrite (parity, I20). The
migration revokes `UPDATE` and `DELETE` from the module role and grants `DELETE`
to a new `clarity_audit_custodian` role that `clarity_app` is not a member of.
Restore and archival declare the privilege through `UnitOfWork.as_custodian()`.

**Phase 2 cross-anchor.** `ReceiptPayload.audit_anchor` carries the current signed
checkpoint inside the signed payload. Receipt schema 1.1, with `compute_hash`
excluding the field for 1.0 payloads. `anchor_verifies` checks one against the
published key. `GET /v1/receipts/{id}/verify` reports it separately.

## Why

The plan's last two open items. Both had real reasons for deferral and the user
asked for them anyway, which is their call.

## Decisions made

ADR-0034 and ADR-0035 amendments carry the substance. Three worth repeating:

- **The upsert was the actual blocker, not the grants.** `ON CONFLICT DO UPDATE`
  needs `UPDATE` whether or not it updates, so revoking it would have broken every
  append. An insert-only path for these collections removes the block.
- **"From the writing role" is the precise wording and I kept it.** Restore and
  archival legitimately delete audit rows, so the answer is a second role, not a
  blanket revoke. `clarity_app` is deliberately not a member of it.
- **A receipt that verified yesterday has to verify today.** Adding a field to a
  signed payload changes every receipt's hash. Hence schema 1.1 and a version-aware
  `compute_hash`, rather than quietly invalidating signatures already delivered.

## Things found while doing it

- **I first wrote that a conflicting append-only insert should raise
  `AppendOnlyViolation`.** Wrong: on the audit trail it genuinely is a race for a
  sequence number, and `_append_with_retry` depends on seeing `ConcurrentUpdate`.
  The existing mapping was right; I corrected the docstring rather than the code.
- **The tamper tests broke, which was the correct signal.** They overwrite stored
  records to prove `verify()` catches it, and the store now refuses that. They
  take `as_custodian` now, which is honest: append-only stops Clarity's own code,
  and the hash chain still catches whoever goes around it. Both layers, tests for
  each.
- My first cut of the custodian check allowed the overwrite whenever a delete was
  staged first in the same unit, which would have made the privilege an accident
  of statement order. Replaced with the explicit span.

## Docs updated
- [x] ADR-0034 and ADR-0035 amendments
- [x] `CHANGELOG.md`, flagged as money path needing two approvals
- [x] `docs/audit-assurance-plan.md`: both items ticked, revision 12, zero open
- [x] `contracts/openapi.json`, golden snapshot, frontend SDK
- [x] CI: a named `Audit append-only grants` step in the `full` lane

## Tests

`make check` was green at 2380 passed before the final contract regeneration; the
snapshot and SDK were then regenerated and `make contracts-check` passes. New:
`tests/security/test_append_only.py` (9) and
`tests/security/test_receipt_audit_anchor.py` (11), both green.

**Not run:** `tests/integration/test_append_only_grants.py`. No PostgreSQL here, so
it skips. The grants are therefore written and argued, not observed, until a green
`full` lane. Same standing as the Phase 6 restore drill.

## Open issues / next step

- **This needs two approvals before merge** (AGENTS.md section 10): it changes
  `modules/receipts` and the signed receipt payload.
- The `full` lane has never run for any of this work, and there is still no PR.
- Still outstanding and unrelated: `GET /v1/cases` does not exist, so the customer
  case list renders fabricated rows.

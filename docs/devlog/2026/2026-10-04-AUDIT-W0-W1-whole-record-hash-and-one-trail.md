# 2026-10-04 - Audit assurance W0 and W1 - Hash the whole record, keep one trail

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code |
| Work package | `docs/audit-assurance-plan.md` Phase 0 (ADR-0033, ADR-0034), Phase 1 W0 and W1 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | platform.audit, app (container, settings, collections), interfaces.mcp, entrypoints |

## What changed

- **W0, ADR-0033.** `AuditRecord` hash version 2 covers every field, with the
  detail bound through `detail_hash`. New fields `actor_kind`, `session_ref`,
  `occurred_at`, `recorded_at`; `recorded_at` never runs backwards.
- **W1, ADR-0034.** The trail persists through the persistence port
  (`platform.audit`, `platform.audit_head`), so `full` keeps one PostgreSQL
  chain for every process. Appends are ordered and insert-only; a lost race
  retries on the new head.
- An `audit` consumer group records every domain event type, deduplicated.
- The MCP server appends each call to the shared trail as an `agent` action.
- A process verifies the trail before serving and records that it did;
  `CLARITY_AUDIT_BREAK_GLASS` starts it on a broken chain and is recorded.
- A demo reset carries the trail across and records `demo.reset`.

## Why

The plan's G1 and G2. Measured on 2026-10-04: rewriting a record's approver,
type, case, time and amount left `verify()` reporting the chain intact; the
trail was lost on restart, split per process and erased by a reset.

## Decisions made

- **The plan overstated coverage, corrected here.** Revision 2 said a dozen
  places wrote to the ledger. Only three event types were ever appended (turns,
  rule publications, switch overrides); the MCP server kept a private list.
  Recording the domain events from the bus closes most of that in one place,
  instead of editing every module.
- **Floats are rendered, not refused.** The canonical hasher rejects floats to
  protect money (I3). Conversation details carry confidence scores, which the
  version 1 hash never looked at; version 2 hashes the detail, so the ledger
  renders floats with `repr` and stores the detail in that form.
- **The unexplained mock-store rows were stashed, not used.** They persisted
  the version 1 hash and only worked in the mock store. Kept recoverable with
  `git stash`; nothing depends on them.
- **Database-level append-only is not done.** The PostgreSQL row store writes
  with `INSERT ... ON CONFLICT DO UPDATE` (checked), which needs UPDATE, so
  revoking UPDATE from the writer needs an insert-only write path first. There
  is no PostgreSQL in this container to verify it against either, so it stays
  an open checkbox rather than an untested claim.
- ADR numbers 0033 and 0034: 0032 stays reserved by `plan.md`.

## Docs updated

- [x] MODULE.md of: none; `platform` has no MODULE.md
- [x] ARCHITECTURE.md / modules.md: no structural change (no new module yet; `modules/assurance` arrives in Phase 4)
- [x] CHANGELOG.md: Changed, Added and Fixed entries
- [x] ADR-0033, ADR-0034 and the ADR index
- [x] `docs/audit-assurance-plan.md`: revision 3, checkboxes, writers row corrected
- [x] `.env.example`: `CLARITY_AUDIT_BREAK_GLASS`

## Tests

- `make check`: ruff and format clean, `mypy --strict` clean (216 files),
  import contracts 3 kept 0 broken; **`1 failed, 2013 passed, 544 skipped`**.
  The failure is `test_an_outbound_connection_is_refused`, the container-proxy
  case that fails identically on the base commit and passed in CI on PR #48.
- New: one test per field version 1 left unprotected (10), removal from the
  middle and from the end, a write around the ledger, two ledgers on one store
  making one chain, survival across a new ledger object, a backwards clock, a
  backdated record; and in `test_audit_trail_wiring.py` domain events reaching
  the trail, a real redelivery recorded once, the trail surviving a reset, MCP
  calls in the trail, a broken chain stopping startup, and break-glass.
- The parity suites for `full` skip here (no PostgreSQL); CI's full lane runs
  them against the new collections.

## Open issues / next step

- W2: identity and access events (sign-in, failures, staff session, refresh,
  403) and the coverage contract test.
- Database-level append-only (above).
- Phase 2: signed checkpoints, the only thing that catches an insider who
  rewrites every record and the head together.

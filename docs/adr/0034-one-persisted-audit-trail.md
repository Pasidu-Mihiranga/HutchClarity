# 0034 - One persisted audit trail for every process

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Thanoj Buddhima |
| Plan references | `docs/audit-assurance-plan.md` (G2, W1), ADR-0013, ADR-0014, ADR-0029, I7 |

## Context

The audit ledger was a Python list inside one process:

- **Lost on restart.** Nothing persisted it in either profile, and `verify()`
  then reported the empty remainder as intact.
- **Split across processes.** `entrypoints/mcp_asgi.py` builds its own
  container, so the API and the MCP server each kept a private chain. The MCP
  server did not even use the ledger: it kept calls in its own list.
- **Mostly unused.** Only conversation turns, rule publications and kill-switch
  overrides were ever appended. Decisions, executions and receipts were
  published on the bus and never audited.
- **Erased by a demo reset**, which built a fresh store.

## Decision

1. **The trail lives behind the persistence port** (ADR-0013): collections
   `platform.audit` and `platform.audit_head`. In `full` they are PostgreSQL
   tables, so every process appends to one chain; in `lite` the in-memory
   driver serves the same code.
2. **Appends are ordered and insert-only.** One unit of work reads the head
   pointer, writes the next sequence number under a fresh key and moves the
   head. Two writers racing for a number cannot both commit: the loser gets
   `ConcurrentUpdate` and retries on the new head. A row already at the next
   number raises `AppendOnlyViolation`.
3. **Domain events reach the trail from the outbox.** An `audit` consumer group
   subscribes to every event type. The outbox row was committed with the state
   change (I7, ADR-0014), so the record cannot be lost between them, and the
   consumer framework's deduplication makes a redelivered event one record.
4. **Fail closed.** An append that cannot be written after its retries raises
   `AuditUnavailable`, and the operation that asked for it fails with it.
5. **Verify before serving.** A process verifies the trail when it starts and
   refuses to serve on a broken chain. `CLARITY_AUDIT_BREAK_GLASS=true` starts
   it anyway for an incident, and that start is recorded.
6. **A demo reset carries the trail across** and records `demo.reset`.
7. **The MCP server writes to the shared trail**, actor kind `agent`, with its
   arguments hashed and never stored.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| A dedicated audit service | New infrastructure, against the maintainer's constraint, and a network hop on every write. The persistence port already gives one ordered store. |
| Write-once storage (WORM) | Infrastructure. Tamper resistance comes from signed checkpoints with a key outside the database instead (plan, Phase 2). |
| Each module appends directly, no consumer | Every module has to remember, and most did not. The bus already carries the facts. |
| A database sequence for `seq` | Ties the ledger to PostgreSQL; the head pointer works on both drivers and passes their parity suite. |

## Consequences

- Every published domain event is in the trail, as its own audit type where
  one exists and as `event.published` otherwise.
- Database-level enforcement (revoking UPDATE and DELETE from the writing role
  on `platform.audit`) is **not done yet**: the generic row store writes with
  an upsert, which needs UPDATE. It needs an insert-only write path and is
  tracked in the plan. Until then append-only is enforced by the ledger and by
  verification, not by the database.
- Identity events, the coverage contract test, checkpoints and the dashboard
  are later work packages in the plan.

## Compliance

`tests/unit/test_audit_trail_wiring.py` checks that events reach the trail,
redelivery is recorded once, the trail survives a reset, MCP calls land in it,
and a broken chain stops startup. `tests/unit/test_events_and_audit.py`
checks one chain for two writers on one store and survival across a new ledger
object.

## Amendment, 2026-10-04: the database enforces append-only

W1 asked for `UPDATE` and `DELETE` to be revoked on the audit tables from the
writing role, and sat blocked because the generic row store writes with
`INSERT ... ON CONFLICT DO UPDATE`. A statement carrying that clause needs the
`UPDATE` privilege whether or not it ever updates anything, so revoking it would
have broken every append rather than only a rewrite.

Resolved by giving append-only collections a write path that plainly inserts
(`APPEND_ONLY` in `persistence.schemas`, honoured by both drivers so `lite` and
`full` behave alike, I20). The conflicting-insert error keeps its existing meaning,
`ConcurrentUpdate`, because on the audit trail it genuinely is a race for a
sequence number and `_append_with_retry` is written to handle it. What changes is
that the loser can no longer overwrite the winner's row.

The migration then revokes `UPDATE` and `DELETE` from the module role and grants
`DELETE` to `clarity_audit_custodian`, which `clarity_app` is deliberately not a
member of. The two operations that legitimately remove audit rows, restoring a
backup (ADR-0038) and sealing a segment (ADR-0039), declare it through a named
`as_custodian` span, so the privilege is visible at the call site and greppable
rather than an accident of whether a delete happened to be staged first.

`platform.audit_head` and `platform.audit_floor` are deliberately not append-only:
they are pointers, they move by design, and they hold no history.

None of this replaces the hash chain, which is what still catches someone who goes
around the application entirely; the tamper tests take the custodian span to stage
exactly that. Grants asserted in `tests/integration/test_append_only_grants.py`
(`full` lane, not yet executed here); the application guard in
`tests/security/test_append_only.py`.

## Amendment, 2026-10-04: the span assumes the custodian role

The amendment above granted `DELETE` to `clarity_audit_custodian` and told
restore and archival to take `as_custodian`. The PostgreSQL driver left that
span empty. A unit of work runs as `clarity_app`, that role is not a member of
the custodian, and the database refused the `DELETE`. The destroy-and-restore
drill failed with `permission denied for table audit` the first time it was run
against PostgreSQL. Archival would have failed the same way.

`as_custodian` now executes `SET LOCAL ROLE clarity_audit_custodian` for the
span and `SET LOCAL ROLE clarity_app` when the span ends without having
committed. `SET ROLE` is authorised against the session user, not the current
role, so the database owner can assume the custodian while `clarity_app` still
cannot inherit `DELETE`. A connection that logged in as the application role
cannot enter the span. No new login and no new infrastructure: the pool already
connects as the owner so that it can assume `clarity_app`.

The custodian is also granted `USAGE` on the `bigserial` sequences, and
`SELECT`, `INSERT`, `UPDATE` and `DELETE` on `platform.audit_head` and
`platform.audit_floor`. Those pointers are rewritten inside the same span, and
once the transaction has assumed the custodian the application role's grants
are not in force. The pointers hold no history. The append-only tables still
do not grant the custodian `UPDATE`.

# 2026-10-04 - AUDIT W1 - custodian span assumes the role

| Field | Value |
|---|---|
| Author(s) | agent: Grok |
| Work package | audit assurance plan W1, Phase 6 restore, Phase 7 archival |
| PR / commit | feat/audit-custodian-span |
| Units touched | platform persistence, platform audit |

## What changed

- `PostgresUnitOfWork.as_custodian` runs `SET LOCAL ROLE clarity_audit_custodian` for the span and returns to `clarity_app` afterwards.
- The migration grants the custodian `USAGE` on the audit sequences, and `SELECT`, `INSERT`, `UPDATE` and `DELETE` on `platform.audit_head` and `platform.audit_floor`.
- The append-only grant test now drives that span. The PostgreSQL restore drill empties the tables through the same span.
- `CustodianUnavailable` is raised when the database login cannot assume the role.

## Why

Restore and archival call `as_custodian` and then `DELETE` audit rows. The PostgreSQL driver treated the span as a no-op, and `clarity_app` is not allowed to delete those rows. The destroy-and-restore drill failed with `permission denied for table audit`. `SET ROLE` is authorised against the session user, so the owner connection can assume the custodian without making `clarity_app` a member of it.

## Decisions made

- No second database login. The pool already connects as the owner so it can assume `clarity_app`. The same session user assumes the custodian, and only inside the span.
- The custodian may write the head and floor pointers because those statements run inside the span, after the application role's grants have been set aside. The pointers hold no history. The append-only tables still grant no `UPDATE` to the custodian.

## Docs updated

- [x] ADR-0034 amendment
- [x] ARCHITECTURE.md status line
- [x] `docs/audit-assurance-plan.md` revision 13
- [x] CHANGELOG.md
- [ ] MODULE.md: persistence and audit live under `platform/`, which has no `MODULE.md`

## Tests

`CLARITY_TEST_DATABASE_URL` set to a throwaway PostgreSQL 18. `pytest tests/integration/test_append_only_grants.py tests/integration/test_audit_restore_drill.py tests/security/test_append_only.py tests/security/test_audit_recovery.py`: 47 passed.

## Open issues / next step

- The receipt cross-anchor is a money-path change and still needs two approvals before merge.
- RPO and RTO remain maintainer decisions (plan section 8).
- The branch was 22 commits behind `origin/main`, with a content conflict in `CHANGELOG.md`, when this was written.

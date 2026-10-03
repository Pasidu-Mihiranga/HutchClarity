# 2026-10-04 - B05 - Restore data ownership for four modules

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) found the defect, wrote the fix, the guard and this entry |
| Work package | B05 (issue #6), ADR-0013, invariant I6 |
| PR / commit | #6 |
| Units touched | platform/persistence, tests/architecture |

## What changed

- `OWNERS` in `clarity/platform/persistence/schemas.py` gained `knowledge`,
  `autopsy`, `deskops` and `insights`.
- New `backend/tests/architecture/test_data_ownership.py`: eight checks that
  `ALL_COLLECTIONS` and `OWNERS` agree, none of which needs a database.
- A comment recording why those four modules are deliberately **not** in
  `CUSTOMER_SCOPED`, since the omission otherwise looks like the same oversight.

## Why

The `full` profile could not start. `create_schema` raised
`UnknownCollection: no module owns 'knowledge.sources'` and every PostgreSQL
test errored out, so I6 ("each module owns its data; one schema and role per
module") was not being enforced for a quarter of the modules.

K01, AU01, D01 and I01 each added collections to `ALL_COLLECTIONS` in the
composition root, which is the list the drivers iterate, and none of them added
the matching prefix to `OWNERS`, which is the list the migration iterates. Two
lists that must agree, with nothing checking that they did.

It survived four work packages because the only test that exercised the mapping
needed PostgreSQL and therefore skipped in the default lane. `make check` was
green the whole time. It surfaced only when the full lane was run locally while
verifying issue #6 for closure.

## Decisions made

1. **The guard needs no database.** A data-ownership rule enforced only in a
   lane most runs skip is not enforced. The new tests import the two lists and
   compare them, so they run in `make check` on every change.
2. **None of the four is customer-scoped, for four different reasons.**
   `knowledge.*` holds published policy documents with no customer in them;
   `insights.projections` holds folds across every subscriber, so it belongs to
   none; `deskops.batches` spans many subscribers and a per-subscriber policy
   would hide the batch from the desk that owns it; `autopsy.complaints` carries
   no `subscriber_ref` at all, because the autopsy is aggregate-facing by
   construction and masking is what protects it. Written down in the file rather
   than left as an absence.
3. **`test_no_owner_entry_is_dead` is bidirectional.** A prefix nothing stores
   is a grant nobody reviews, so the two sets must be equal, not merely
   contained.

## Docs updated

- [ ] MODULE.md - no module's own surface changed
- [ ] ARCHITECTURE.md / modules.md - no structural change
- [ ] CHANGELOG.md - no public surface or `/v1` change
- [x] This devlog entry

## Tests

```
backend/tests/architecture/test_data_ownership.py   70 passed
make check                                          1863 passed, 544 skipped
full lane (contract + integration, live stack)      1127 passed, 10 skipped
```

Before the fix the full lane errored on 30 tests across
`test_postgres_isolation.py`, `test_postgres_rls.py`, `test_two_replicas.py`
and the `[postgres]` parametrisation of `test_repository_parity.py`.

Two non-vacuity probes:

| Probe | Tests that failed |
|---|---|
| remove `knowledge` from `OWNERS` (the original defect) | both parametrised ownership checks for `knowledge.sources` and `knowledge.chunks`, dead-entry, distinct-table, regression guard |
| typo an owner name (`insights` to `insigths`) | named-for-its-owner, every-owner-is-a-real-module |

The 10 remaining full-lane skips are the pgvector hybrid retriever, blocked on
`ModelRole.EMBED` having no implementation (recorded in the K02 devlog). That is
a known gap, not a new one.

## Open issues / next step

- The full lane is only run in CI. It caught nothing for four work packages
  because nobody ran it locally; the new architecture tests close that specific
  hole, but the general lesson is that a skipped lane is an unverified one.
- Local stack ports differ from CI: PostgreSQL is on 5440, not 5432, and the
  OpenBao token is `clarity-development-only`. Worth a `make test-full` target
  so the next person does not rediscover it.

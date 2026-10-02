# 2026-10-02 - B02 - Unit of work and repository interfaces per module

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | B02 (issue #5), Wave 0 baseline wiring; plan 21 section 11.6 R2a.2, ADR-0013 |
| PR / commit | issue #5 |
| Units touched | platform (new `persistence`), case, actions, receipts, governance, app |

## What changed

- New `clarity.platform.persistence`: `UnitOfWork` and `Repository` ports, typed faults (`ConcurrentUpdate`, `UnitOfWorkClosed`), and an in-memory driver with per-row versions.
- `AutocommitRepository` for state a service changes one record at a time, so all state sits in the store without inventing transaction boundaries the domain does not have yet.
- Four modules now take a repository by injection and keep no collection of their own:
  - case: `CaseRepository` over `case.records` and `case.sequence`; `CaseRecord` extracted to `records.py`.
  - actions: `PlanRepository` over `actions.plans`; `PlanRecord` and `FOUR_EYES_THRESHOLD_LKR` extracted to `records.py`.
  - receipts: `ReceiptRepository` over the chain, the supersession map, the subscriber map and the sequence; the `_Ledger` dataclass is gone.
  - governance: `PolicyChangeRepository` over `governance.changes`; `PolicyChange` and its vocabulary extracted to `artefacts.py`.
- `app.container` builds one `MemoryStore` and binds every repository from it. It remains the only place that chooses a driver (I20).
- Services write a record back after mutating it, so a driver that stores a copy (B05) sees every change.
- `tests/support/repositories.py` builds the same seam for tests, so no test uses a dict the production path does not.

## Why

Issue #5: module state lived in ad-hoc dicts inside `CaseService`, `ToolLayer` and the receipt ledger, so nothing could be persisted, rolled back or shared across replicas. ADR-0013 names the repository interface as the seam, and B05 adds the PostgreSQL driver behind it.

## Decisions made

- **Each module declares its own repository protocol** over its own record type, and `public.py` exports it. The generic `Repository` stays small; the domain-shaped protocol gives B05 a clean target and keeps the module boundary (I5) owned by the module.
- **Records extracted from the services that use them** (`records.py`, `artefacts.py`). A repository protocol must name what it stores, and importing the service would be a cycle.
- **Autocommit rather than retrofitted transaction spans.** Explicit unit-of-work boundaries across the money path are B04 (#12) and M-ACT (#25). Opening them here would have changed behaviour the R0 suite pins, for no gain until the outbox is wired.
- **Insert-against-insert counts as a conflict**, not last-writer-wins. Two replicas proposing the same plan id must not both succeed.
- **Three collections are deferred, not exempted.** Budget reservations and confirmation tokens belong to M-ACT (#25), shared OTP state to M-IAM (#7). They are listed in `DEFERRED` in `tests/architecture/test_module_state.py` against the issue that owns them, so the limitation fails loudly if the owning issue is dropped, and a new unowned collection fails the test outright.

## Docs updated

- [x] MODULE.md of: case, actions, receipts, governance (Files, Data owned, Change history; case also Public surface)
- [ ] ARCHITECTURE.md / modules.md: no structural or status change (the modules are the same units, same layer)
- [ ] Walkthrough: no user-visible flow changed
- [ ] CHANGELOG.md / contracts: no `/v1` contract change; the OpenAPI snapshot test is unchanged and green
- [ ] Plan via CHANGES.md: implements plan 21 section 11.6 as written, no plan change

## Tests

- New `backend/tests/contract/test_repository_parity.py`: 15 tests, the contract every driver must pass. Covers the two acceptance cases the issue names (a rolled-back case does not exist; two units of work updating one plan give the second a typed `ConcurrentUpdate`), plus read-your-writes, isolation before commit, insertion order, delete, and use after close.
- New `backend/tests/architecture/test_module_state.py`: the grep test the Definition of Done asks for, plus a check that each deferral still applies so the map cannot rot.
- Verified both new tests are not vacuous: disabling the version check fails the parity suite, and reintroducing a `dict` attribute in `CaseService` fails the state test.
- `make check`: lint, format, `mypy --strict` (159 files), 3 import contracts kept, **605 passed**. The R0 acceptance suite passes unchanged, which is acceptance test 3.

## Open issues / next step

- B05 (#6) adds the PostgreSQL driver and must pass `test_repository_parity.py` unchanged; it also brings schema and role per module and row-level security.
- B04 (#12) wires outbox rows into the same unit of work as the state change, which is the first caller that needs an explicit transaction span rather than autocommit.
- M-ACT (#25) moves budget counters, reservations and confirmation tokens to the database with row locks, clearing three of the five `DEFERRED` entries.
- M-IAM (#7) moves shared OTP state, clearing the other two.

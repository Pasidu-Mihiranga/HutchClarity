# 2026-10-04 - C2 (F05) - foresight starts remembering

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code, for Pasidu Mihiranga |
| Work package | C2 (workstream C, plan item F05) |
| PR / commit | branch `feat/foresight-persistence`, stacked on C1 |
| Units touched | foresight, platform/persistence (schema registry only), app/collections, app/container |

## What changed

- **New `records.py`.** `ScenarioVersion`, `ScenarioRun` with `RunStatus`, `StoredReport`, `StoredLaunch`, `RecordedOutcome`, `StoredCalibration`, `DetectedSpike` with `SpikeScope`.
- **New `repository.py`.** Seven collection names, the `ForesightRepository` protocol and `StoredForesightRepository` over the platform driver, modelled on `modules/autopsy/repository.py`.
- **New `service.py`.** `draft`, `revise`, `request_run` (idempotent), `execute`, `record_launch`, `record_outcome`, `backtest`, `record_spike`, and readers.
- **`platform/persistence/schemas.py`:** `"foresight": "foresight"` in `OWNERS`; six collections added to `APPEND_ONLY`; the "deliberately not customer-scoped" note extended to foresight.
- **`app/collections.py`:** all seven listed, which is what gives them a table, a role grant and (not, here) a row-level security policy.
- **`app/container.py`:** builds `clarity.foresight_service`.

## Why

Plan workstream C, item C2: "Seven collections, `"foresight": "foresight"` in `OWNERS`, six of the seven append-only. Nothing customer-scoped, by construction."

Before this, a foresight run was built, returned and discarded. Nothing could be cited later, two people could not look at the same rehearsal, and the calibration gate had nowhere to keep the evidence it is supposed to open on. C1 came first because a scenario could not be stored while its `scenario_id` changed on every read.

## Decisions made

- **Which six are append-only, and why `runs` is not.** A run has a lifecycle a caller polls, so its row moves by design; an append-only job record is the same contradiction as the append-only pointer the audit ledger already excludes. Everything else is either something somebody asked for, something the engine produced, or evidence about a change that shipped, and none of those gets to change after the fact.
- **Outcomes are their own rows, not a list on the launch.** An outcome recorded late is then an insert rather than a rewrite. An append-only launch could not take the rewrite, and a launch replaced to add an observation would lose who recorded the earlier ones.
- **A scenario family and a scenario version are different identifiers.** `scenario_id` is the family and is shared by every version; `version_id` is the row. A run cites a version, so a revision cannot change what an already-stored run claims to have rehearsed. `next()` refuses a scenario from a different family.
- **Two "run" identifiers, named apart.** `ScenarioRun.run_id` is the job a caller polls; `ForesightReport.run_id` is the engine's own identifier for one computation, stored as `StoredReport.report_id`. A test asserts they differ, because a reader who conflates them looks for a report under a job id and does not find one.
- **`request_run` returns `(run, is_new)`.** That is what lets C4 answer `202` for a new run and point a repeat at the original rather than pretending it just created one (I8). The risk foresight carries is a double *finding*, not a double charge.
- **`record_launch` refuses `Provenance.REAL` outright**, rather than accepting it and leaving the locks to C6. An ungated way to write the evidence is worth more to somebody wanting a green gate than the gate is worth to anybody else, so there is no window where the path is open. It refuses rather than downgrading to `SYNTHETIC`: a caller whose evidence silently did not count would find out at the gate.
- **A report rests on the latest stored calibration**, attached by the service. A report that chose its own backtest could be made to look decision-ready by handing it a friendlier one.
- **A failed run is recorded, not discarded.** A rehearsal that could not be computed is a thing a product manager needs to see, and a job that vanishes reads as one that was never asked for.
- **Lookups scan `values()`.** The platform repository is deliberately small, and this is what `autopsy` does too. A rehearsal is a human-initiated act, not a per-request one. If that stops being true the answer is an index in the driver, not a second copy of the data in the module.

### A note on the plan's assumption

Plan C2 says these "would be the first non-audit entries in `APPEND_ONLY` (currently only `platform.audit*`), so the migration grants need extending". That is now stale: A4 added `conversation.transcripts`, and the grant machinery in `migrations.py` is generic over `APPEND_ONLY`. No migration code changed. The grants were verified by reading them back out of `information_schema` rather than by assuming.

## Docs updated

- [x] `MODULE.md` of: foresight (public surface, used-by, dependencies, the data-owned table, invariants, migration status, tests, history)
- [x] This devlog
- [x] `CHANGELOG.md` (the module's public surface gained the service, repository and collection names)
- [ ] `docs/modules.md` / `ARCHITECTURE.md`: not needed. No new module and no new dependency **between modules**; foresight remains a leaf, as plan 21 section 11.2 already records.
- [ ] Plan via `CHANGES.md`: not needed. Plan 21's data model does not enumerate per-module collections.
- [ ] Walkthrough: not needed, no user-visible flow changed yet. C4 adds the routes.
- [ ] ADR: none. The append-only choice follows ADR-0013 and ADR-0034 rather than changing them.

## Tests

- `tests/unit/test_foresight_persistence.py`: 68 new tests. Ownership and scoping of all seven collections, append-only enforcement on a scenario version and a recorded outcome, the run lifecycle, idempotency including a repeat after the run finished, the refusal to record a real launch, backtest assembly from stored outcomes, and the radar record's codes-only shape.
- `make check`: **2681 passed, 640 skipped** (2599 before this change), ruff, mypy --strict over 249 files, import contracts 3 kept 0 broken.
- **PostgreSQL integration tests run for real**, not skipped: a local PostgreSQL 16 was started and `CLARITY_TEST_DATABASE_URL` set. `tests/integration` passed, and the grants were read back directly:

  ```
  foresight.calibrations  ['INSERT', 'SELECT']
  foresight.launches      ['INSERT', 'SELECT']
  foresight.outcomes      ['INSERT', 'SELECT']
  foresight.reports       ['INSERT', 'SELECT']
  foresight.scenarios     ['INSERT', 'SELECT']
  foresight.spikes        ['INSERT', 'SELECT']
  clarity_foresight tables: calibrations, launches, outcomes, reports, runs, scenarios, spikes
  ```

  `foresight.runs` is absent from the append-only report, which is what keeps its `UPDATE`.

One pre-existing test fails under this session's network proxy and passes without it: `tests/unit/test_cassettes.py::test_an_outbound_connection_is_refused`. Unrelated.

## Open issues / next step

- C3: the persona simulator port and its three drivers. Independent of this; both stack on C1.
- C4: the API over this service. `request_run` already returns the `(run, is_new)` pair its `202` needs.
- C6: the four locks on real-launch evidence. `StoredLaunch` already carries `provenance` and `evidence_ref` for them to be enforced against; `record_launch` refuses `REAL` until then.
- `ForesightService` readers each open their own unit of work. That is fine at these volumes and matches `autopsy`, but a route that calls three of them does three transactions; C4 should pass one unit where it matters.

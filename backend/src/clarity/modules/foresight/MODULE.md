# foresight - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.foresight`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `public.py`, `catalogue.py`, `simulation.py`, `backtest.py`, `personas.py`, `rehearsal.py`, `records.py`, `repository.py`, `service.py` |

## 1. Purpose
Foresight: scenario simulation over aggregates only, reported as relative bands, not counts, plus the backtest that measures how wrong the baseline was and refuses to call that a calibration.

## 2. Public surface (`public.py`)
Other code imports only `public.py`: the baseline and backtest names, C1's `ForesightCatalogue`, `Bands`, `ThemeCatalogue`, `ThemeWeight`, `PersonaRounds` and `CatalogueInvalid`, and C3's `PersonaSimulator`, `Propensity`, `PersonaRun`, the three drivers, `PersonaRehearsal`, `RehearsalReport` and `PairComparison`.

`PersonaSimulator` is the port: `propensities(scenario, *, seed) -> PersonaRun`, returning a share of **one segment** in [0, 1] per theme-segment pair. Never a band, never a count. Three drivers implement it: `StatisticalBaseline` (the historic-rate method, which is also what `Foresight` reports), `RoundBasedPersonaSimulator` (seeded cohorts stepped through awareness, standard library only) and `LlmPersonaSimulator` (an in-house persona prompt over the `reason` role).

`PersonaRehearsal(catalogue, comparison=None)` runs the baseline as the headline and optionally a second method beside it. It takes **no** headline argument; see ADR-0043.

`ForesightCatalogue(policies)` reads the module's parameters from the policy store. It is the only thing `Foresight` and `Backtest` need wired, and the composition root builds one per container.

`Foresight(catalogue, clock=None).run(scenario, calibration=None)` returns a `ForesightReport`. `Backtest(catalogue, clock=None).run(launches)` replays recorded launch outcomes through the baseline and returns a `CalibrationReport`: mean absolute and signed band error, exact-band rate, top-theme hit rate, the pairs it could not compare, and a status.

`Scenario` is frozen, carries a real `scenario_id` field and a **required** `effective_date`. The whole run resolves policy `as_of` that date.

`ForesightService(open_unit=, catalogue=, clock=)` is the stored surface (C2): `draft`, `revise`, `request_run` (idempotent, returns `(run, is_new)`), `execute`, `record_launch`, `record_outcome`, `backtest`, `record_spike`, and readers for each. The composition root builds one as `clarity.foresight_service`.

`ForesightRepository` / `StoredForesightRepository` are the persistence protocol and its implementation, plus the seven collection names exported as `FORESIGHT_SCENARIOS`, `FORESIGHT_RUNS`, `FORESIGHT_REPORTS`, `FORESIGHT_LAUNCHES`, `FORESIGHT_OUTCOMES`, `FORESIGHT_CALIBRATIONS` and `FORESIGHT_SPIKES`.

### Changed in C1 (breaking)
| Was | Is | Why |
|---|---|---|
| `Foresight()` | `Foresight(catalogue, clock=None)` | Parameters are policy, not constants (I10); time is injected (I11) |
| `Backtest()` | `Backtest(catalogue, clock=None)` | The calibration gate resolves from policy |
| `ScenarioRehearsal()` | `ScenarioRehearsal(catalogue)` | Builds the baseline it compares against |
| `Scenario.scenario_id` (`@property`) | `scenario_id` field | The property returned a new id on every read, so a scenario could not be stored or cited |
| `Scenario.effective_date: str \| None` | `effective_date: date`, required | It is what the run resolves policy at; it was free text nothing read |
| `Scenario.segments` defaults to `DEMO_SEGMENTS` | defaults to `None`, meaning the policy catalogue at `effective_date` | The segment mix is policy |
| `MIN_REAL_LAUNCHES`, `DEMO_SEGMENTS` exported | removed | A constant beside a policy key is the one that gets read by mistake (D2) |

### Changed in C3 (breaking)
| Was | Is | Why |
|---|---|---|
| `swarm.py`, `ScenarioRehearsal`, `SeededPersonaSimulator`, `SwarmReport`, `Comparison` | removed; `personas.py` and `rehearsal.py` | The "swarm" hashed `seed:scenario:theme:segment`, took two hex digits modulo three minus one, shifted the baseline's band by that, and compared the result against a second run of the same baseline. It measured a hash. |
| `PersonaSimulator.run(scenario, *, seed) -> tuple[Prediction, ...]` | `propensities(scenario, *, seed) -> PersonaRun` | Drivers return propensities so they are comparable and so banding stays in the module (ADR-0043) |

## 3. Used by
`clarity.app.container` (builds the catalogue, engine, backtest and service), `clarity.app.collections` (the seven collection names) and `clarity.interfaces.http` (`GET /v1/demo/foresight`). No other module calls it, and it calls none: foresight is a leaf (plan 21 section 11.2).

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.kernel` | `money`, `new_id` |
| `clarity.platform.config` | `PolicyResolver`, for every tunable (I10) |
| `clarity.platform.content` | `content.foresight`, for mitigation and caveat wording |
| `clarity.platform.persistence` | `Repository`, `UnitOfWork`, for the seven collections |

## 5. Data owned
Seven collections in the `clarity_foresight` schema, with their own role (I6, ADR-0013). **Nothing is customer-scoped**, by construction: foresight reads segment statistics and never an individual record (deck S8), so there is no `subscriber_ref` to bind a row to.

| Collection | Holds | Append-only |
|---|---|---|
| `foresight.scenarios` | One row per `ScenarioVersion`; a change is a new version | yes |
| `foresight.runs` | `ScenarioRun`: queued, running, succeeded or failed | **no** |
| `foresight.reports` | `StoredReport`, one engine output per run | yes |
| `foresight.launches` | `StoredLaunch`: a rehearsed change that shipped | yes |
| `foresight.outcomes` | `RecordedOutcome`, one observed theme-segment band | yes |
| `foresight.calibrations` | `StoredCalibration`, one backtest | yes |
| `foresight.spikes` | `DetectedSpike` from the radar (C5 supplies the detector) | yes |

`foresight.runs` is the one mutable collection, and the exception is the point: a run has a lifecycle a caller polls, so its row moves by design. Everything else is a claim about the past that a later reader relies on. The launches and outcomes matter most, because they are the evidence the plan 02 section 3.4 gate opens on, so they are exactly the rows somebody would have to rewrite to make an uncalibrated engine look calibrated. Append-only is backed by database grants (`INSERT`, `SELECT` and nothing else), read back from `information_schema` by `tests/integration/test_append_only_grants.py`.

Its **parameters** are owned by the policy store, not by this module: `config/policy/foresight.yaml` holds the segment catalogue, the per-change-type theme catalogues, the borrowing map, the band thresholds and the calibration gate.

## 6. Invariants
- Never uses individual customer data; not decision-ready until backtested.
- **No tunable lives in code (I10, D2).** Segments, theme weights, borrowing, band thresholds and the calibration gate all resolve from the policy store, and no constant shadows one. A test asserts the constants are gone.
- **Everything resolves `as_of` the scenario's effective date**, never "now". A rehearsal of an October change uses October's parameters, including a value approved today whose window opens then.
- **A malformed catalogue raises `CatalogueInvalid`** rather than defaulting. A run on half a parsed segment list reports numbers nobody authored, in the same shape as a correct run.
- **A theme driver is an allowlist**, checked at parse time, so a typo cannot reach `getattr` and silently scale by 1.0, and no policy string can name an arbitrary attribute of `Segment`.
- **Borrowed themes are declared in the report.** Seven of the twelve change types have no catalogue of their own; the report names the lender in its caveats instead of presenting another change type's themes as its own.
- **A change type nobody characterised says so.** An empty prediction list carries an explicit caveat, because silence and "we expect no complaints" otherwise look identical.
- **Six of the seven collections are append-only** (C2). A scenario version, an engine output, a launch, an outcome and a calibration are never rewritten; only `foresight.runs` moves.
- **A repeated run request returns the original run** (I8), including its original outcome. The risk foresight carries is not a double charge, it is a double finding: two runs of one scenario reported twice is how a rehearsal gets counted as two pieces of evidence.
- **`record_launch` refuses `Provenance.REAL`** until C6 wires the capability and the required external `evidence_ref`, and it refuses rather than downgrading to `SYNTHETIC`: a caller whose evidence silently did not count would find out at the gate.
- **A report rests on the latest stored calibration**, attached by the service rather than passed in by a caller. A report that chose its own backtest could be made to look decision-ready by handing it a friendlier one.
- **A propensity never sets a reported band** (ADR-0043, C3). The port returns a share of one segment in [0, 1]; banding happens once in the module against the policy thresholds; `PersonaRehearsal` constructs its own baseline and takes no headline argument, so no caller can put a model in charge of a band.
- **An absent comparison is not a zero one.** A driver that could not answer reports `answered=False` and the column is `None`, because a column of zeros reads as the finding that no segment will complain.
- **Agreement between methods proves nothing** and every rehearsal says so: both rest on the same segment catalogue and neither has been calibrated against a real launch.
- Persona rehearsal is seeded and aggregate-only. It emits relative bands,
  records its simulator version and has no executing capability.
- **Error is measured in band steps** (LOW=0, MEDIUM=1, HIGH=2), never in complaints, because bands are all the baseline emits.
- **A synthetic launch never moves the calibration status.** `Provenance.SYNTHETIC` outcomes are the predictor's own assumptions played back; they exercise the method and validate nothing (I16). `CalibrationStatus.CALIBRATED` needs `foresight.calibration.min_real_launches` (3, plan 02 §3.4; tagged regulatory so it is change class C4, with a guardrail that refuses a value under three) launches with `Provenance.REAL`, of which the prototype has none (**REQUIRES HUTCH CONFIRMATION**).
- **Nothing comparable reports no error, not a perfect one.** With zero overlapping (theme, segment) pairs the error fields are `None`; a `0.000` would read as a flawless model. Same shape as an `UNEVALUABLE` evaluation gate.
- **An observed theme the model never predicted is reported, not scored.** It lands in `unpredicted` rather than being treated as a LOW prediction, so under-prediction cannot be averaged away. A prediction with no recorded outcome lands in `unobserved`: absence of a record is not a LOW observation.
- `ForesightReport.backtested` is derived from the calibration handed in, not hard-coded, so the plan §3.4 gate opens on evidence and on nothing else.

## 7. Migration status (enterprise-plan 21)
Uncalibrated by design (states so in every report). Runtime target: serverless batch job. Data target reached in C2: one PostgreSQL schema and role, same repository interfaces on both drivers, verified against a real PostgreSQL.

## 8. Tests
- `tests/unit/test_autopsy_foresight.py`
- `tests/unit/test_foresight_personas.py` (C3: the parity suite over all three drivers, the round-based driver's determinism and policy inputs, the LLM driver's parsing and refusals, and the I1 boundary)
- `tests/unit/test_foresight_catalogue.py` (C1: policy-driven parameters, `as_of` resolution, parse refusals, borrowing, the frozen scenario)
- `tests/unit/test_foresight_persistence.py` (C2: ownership, append-only, versions, idempotent runs, the run lifecycle, evidence, backtest assembly)
- `tests/integration/test_append_only_grants.py` and `tests/integration/test_postgres_isolation.py` cover the seven tables generically, against a real PostgreSQL

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.foresight` with a public surface (R1) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-F01-foresight-backtest-and-calibration.md` | Added `backtest.py`: calibration report, band-step error, the real-launch gate (F01, #27) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-F02-synthetic-scenario-rehearsal.md` | Added seeded aggregate personas and baseline-vs-swarm comparison |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-C1-foresight-policy-and-typed-scenario.md` | Moved every tunable to `config/policy/foresight.yaml` and the wording to `platform/content/foresight.py`; froze `Scenario` with a real id and a required typed `effective_date`; injected the clock (C1/F03) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-C2-foresight-persistence.md` | Seven collections in the `clarity_foresight` schema, six append-only; scenario versions, idempotent runs with a lifecycle, launches, outcomes, calibrations and spikes (C2/F05) |
| 2026-10-04 | `docs/devlog/2026/2026-10-04-C3-persona-simulator-port.md` | Replaced the hash-based swarm with a `PersonaSimulator` port returning propensities, three drivers, and the structural I1 boundary (C3/F04, F11; ADR-0043) |

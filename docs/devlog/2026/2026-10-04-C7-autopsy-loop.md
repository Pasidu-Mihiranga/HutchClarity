# 2026-10-04 - C7 (F10) - closing the loop, without making foresight depend on autopsy

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code, for Pasidu Mihiranga |
| Work package | C7 (workstream C, plan item F10) |
| PR / commit | branch `feat/foresight-autopsy-loop`, stacked on C4 |
| Units touched | contracts/events, foresight, autopsy (publishes one event), app/container, interfaces/http, docs/enterprise-plan |

## What changed

- **`cluster.updated`** in `clarity.contracts.events`, published by `autopsy` on every recorded review, in the same transaction as the verdict (I7).
- **New `loop.py`:** the `ClusterRateSource` port, `ClusterRate`, `OutcomeCandidate`, `AutopsyLoop`, `PairOutcome` and `PostLaunchComparison`. Plus an eighth collection, `foresight.candidates`.
- **`service.py`:** `confirm_candidate` and `comparison`.
- **`app/container.py`:** `_AutopsyClusterRates` implements the port over `AutopsyService`, and the loop is registered as a `cluster.updated` consumer.
- **Three routes:** `GET /v1/foresight/candidates`, `POST /v1/foresight/candidates/{cluster_id}/confirm`, `GET /v1/foresight/launches/{launch_id}/comparison`.
- Plan 21 §11.3 gains the `cluster.updated` row.

## Why

Plan C7. Foresight predicts and `autopsy` finds out, and until now the two never met: a rehearsal could be wrong forever without anybody noticing, and the calibration gate had no source of evidence other than somebody typing one in.

## Decisions made

- **The port is declared in foresight and the driver lives in the composition root**, exactly as the plan says and exactly as `AutopsyService(source=_complaint_source())` already does. This is not squeamishness about an import. A synchronous L4-to-L4 dependency has to be declared in `tests/architecture/test_module_dependencies.py`, plan 21 §11.2, `docs/modules.md`, `ARCHITECTURE.md` and both `MODULE.md` files, and it would make foresight unable to run as the batch job plan 21 moves it to. A test walks foresight's imports with `ast` and fails if `modules.autopsy` ever appears.
- **A cluster never becomes calibration evidence on its own.** This is the part worth being careful about and the plan says so explicitly. A confirmed cluster is a real observation, but it is an observation about complaints, not about a theme in a segment: turning "cluster CL-7 has 40 members" into "`data stopped at cap` was HIGH for students" is an act of interpretation. So `cluster.updated` produces an `OutcomeCandidate` that carries **no theme, no segment and no band**, and a named person supplies all three when they confirm it. A test asserts the candidate has none of those attributes.
- **Confirming twice is refused.** A second confirmation would write a second append-only outcome from one observation, which is how a single cluster would count twice towards the gate.
- **`foresight.candidates` is mutable**, and that is the second collection in this module that is. A candidate has exactly one transition, unconfirmed to confirmed, in the same way a run moves through its status. The evidence a confirmation produces is a `RecordedOutcome`, and *that* is append-only.

  I first wrote this with the candidates collection append-only and the confirmation going through `UnitOfWork.as_custodian()`. That was wrong: the custodian span is the named exception for restoring a backup and sealing an audit segment (ADR-0038, ADR-0039), and spending it on a product note would make it mean nothing. Changed before it shipped.
- **`cluster.updated` carries no label and no keywords.** A cluster's label is derived from what customers wrote, so publishing it would put a paraphrase of complaint text on the bus, and `autopsy` exists precisely so that text stays in one place. A consumer that needs the label asks autopsy.
- **A predicted pair with no recorded outcome is `None`, never LOW.** The backtest already refuses to average absence in; the comparison says the same thing in the shape a person reads, and the API renders it as `null`.
- **Cluster rates are context, never score.** Clusters are not keyed by theme or segment, so they cannot be compared against a prediction. They are in the comparison because a reader asking "was this launch noisy" should not have to open another screen. A test asserts they do not change the comparison.
- **An unreachable complaint side leaves the context empty rather than failing the comparison.** Losing the whole screen because a side panel could not load would be the wrong trade.

## Docs updated

- [x] `MODULE.md` of: **foresight** (files, the `/v1` surface, an events table, the data-owned table with the eighth collection, invariants, tests, history) and **autopsy** (a new "events produced" section, since it now produces one)
- [x] This devlog
- [x] `CHANGELOG.md`
- [x] **New event**: producer contract, plan 21 §11.3 row, sample payload in `tests/support/events.py`
- [x] **`/v1` contract change**: three routes, OpenAPI golden regenerated, `contracts/openapi.json` re-exported, SDK types regenerated, `make contracts-check` passes
- [x] `tests/acceptance/test_route_contract.py`: all three classified
- [ ] `docs/modules.md` / `ARCHITECTURE.md` / the dependency map: **not needed, and that is the point of the design.** Foresight remains a leaf; it consumes an event and reads a container-wired port, neither of which is a synchronous module dependency (ADR-0029).
- [ ] ADR: none. The port pattern follows the existing `ComplaintSource` precedent, and the "a person confirms it" rule is ADR-0044's, which C6 recorded.

## Tests

- `tests/unit/test_foresight_loop.py`: **25 new tests**. The import check that keeps foresight a leaf, the inert candidate and its missing fields, idempotency on replay, that an unconfirmed candidate scores nothing in a backtest, confirmation under a person's name, the double-confirmation refusal, predicted-versus-actual including the `None` case and the exact agreement rate, cluster rates as context that do not change the comparison, the unreachable source, and the event's codes-only shape.
- `make check`: **2968 passed, 782 skipped** (2935 on C4's branch), ruff, mypy --strict over 251 files, import contracts 3 kept 0 broken.
- `make contracts-check`: SDK types match the committed schema.
- **Against a real PostgreSQL 16**: the whole `tests/integration` suite passes with the new collection in place.

## Open issues / next step

- `comparison()` picks the first stored report for the launch's scenario version. A version run twice has two reports, and the comparison would show the earlier one. A launch should probably cite the run it was rehearsed by; that is a field on `StoredLaunch` and a follow-up rather than a change here.
- A candidate is not linked to a launch until somebody confirms it against one. The console will want a way to suggest likely launches; the data is there (effective dates, change types) and the ranking is a product decision.
- `cluster.updated` fires on review only, not when `rerun` draws new hypotheses. That is deliberate for now, since an unreviewed hypothesis is not an observation, but it means foresight sees nothing until somebody reviews.
- This is the last package in workstream C. All seven are open as stacked pull requests.

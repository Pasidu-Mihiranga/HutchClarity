# [F02] Foresight: complete synthetic scenario rehearsal

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `foresight` |
| Priority | P0 |
| Depends on | [DATA01](DATA01-synthetic-telecom-dataset-foundation.md), [F01](F01-foresight-backtest-and-calibration-report.md), [AU02](AU02-autopsy-synthetic-dataset-hardening.md) |
| Plan | 02 §3.4 |
| Labels | `wave:w4`, `area:foresight`, `priority:p0`, `type:feature` |

## Context

Preserve the existing scenario types, segments, relative bands, deterministic
baseline, reports, backtest, provenance protection, real-launch calibration
gate, demo route and console summary. Foresight is a rehearsal tool. Every
result says `SCENARIO, NOT CERTAINTY`; synthetic results say
`NOT CALIBRATED ON REAL HUTCH LAUNCHES`.

## Scope

- Accept only DATA01 aggregates, never individual customers, complaints,
  conversations or transactions.
- Expand synthetic historic launches across pack retirement/migration, price
  and FUP changes, VAS consent, outage, social-pack scope, PAYG, new packs and
  promotion end. Synthetic launches never yield `CALIBRATED`.
- Add authorized scenario management for name, change type, products, affected
  share, severity, segments, effective date and business context.
- Keep the statistical baseline and add a seeded persona/swarm interface with a
  deterministic internal implementation unless an approved OSI-licensed
  adapter is separately justified.
- Simulate segment personas, aggregate immediately and never persist individual
  agent conversations.
- Compare baseline and swarm LOW/MEDIUM/HIGH bands, agreements and differences.
- Report themes, segments, risk rank, mitigations, caveats, comparison,
  backtest, calibration, seed and config/model version without fake counts.
- Keep recommendations advisory with no refund, account, policy, message or
  product-changing capability.
- Compare expected themes with synthetic post-launch Autopsy clusters and show
  anticipated and missed themes.
- Add APIs for UI02 scenarios, results, backtests and calibration.

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | DATA01 output | loaded | only aggregate input is accepted | `backend/tests/architecture/test_foresight_aggregate_only.py` |
| 2 | an authorized user | a scenario is configured | it is rehearsed with seed and config version | `backend/tests/acceptance/test_foresight_workspace.py` |
| 3 | a core change type | baseline and swarm run | both emit themes and relative bands | `backend/tests/unit/test_foresight_swarm.py` |
| 4 | identical seed/config | run twice | aggregate results match | `backend/tests/unit/test_foresight_swarm.py` |
| 5 | a report | viewed | mitigations, caveats and comparison appear without precise counts or execution capability | `backend/tests/acceptance/test_foresight_workspace.py` |
| 6 | synthetic launches | backtested | metrics exist and calibration stays closed | `backend/tests/unit/test_autopsy_foresight.py` |
| 7 | synthetic launch and Autopsy output | compared | anticipated and missed themes carry synthetic provenance | `backend/tests/integration/test_foresight_autopsy_loop.py` |
| 8 | any synthetic result | shown in Desk | scenario and calibration warnings are visible | `frontend/e2e/foresight.spec.ts` |

## Definition of Done

- [ ] Acceptance tests exist and pass; `make check` is green
- [ ] Intentional API changes update OpenAPI, SDK and CHANGELOG.md
- [ ] Foresight and consumer `MODULE.md` files, devlog and walkthrough are updated
- [ ] New dependencies have an OSI licence check
- [ ] No secrets or real personal data; simulated parts are labelled

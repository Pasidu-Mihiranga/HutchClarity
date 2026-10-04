# 2026-10-04 - DATA01 - synthetic dataset foundation

| Field | Value |
|---|---|
| Author(s) | agent: Codex wrote the code, tests and this entry |
| Work package | DATA01 |
| PR / commit | not committed |
| Units touched | integration, developer tooling |

## What changed

- Added a fixed-seed synthetic corpus covering all 18 target cause families and
  unknown cases, with multilingual wording and separate operational facts.
- Added evaluation-only ground truth, missing-evidence cases, repeated contacts,
  duplicates and aggregate-only Foresight records.
- Added `make synthetic-data`; generated exports are ignored and reproducible.

## Why

The company approved synthetic, anonymous data for the prototype and prohibited
real customer data. DATA01 replaces tiny disconnected examples with a coherent
foundation while keeping `hutch-sim` as the integration seam.

## Decisions made

- The dataset labels all 18 target families but does not claim that all 18 rule
  packs are implemented.
- Ground truth and complaint text remain structurally separate from operational
  evidence. Foresight receives a separate aggregate shape.

## Docs updated

- [x] ARCHITECTURE.md and docs/modules.md
- [x] DATA01 backlog issue and Makefile help
- [ ] Module `MODULE.md`: integration has no module document
- [ ] Walkthrough and CHANGELOG.md: no user flow or public `/v1` contract changed

## Tests

- `backend/tests/unit/test_synthetic_dataset.py`: 6 passed
- `make synthetic-data`: 1,500 complaints, 1,338 evidence events; identical
  digest on repeat generation
- `make check`: Ruff and formatting clean; mypy strict clean across 218 source
  files; 3 import contracts kept; 2,000 passed, 544 skipped in 52.14s.

## Open issues / next step

- AU02 will ingest this corpus through the existing mask-first Autopsy service.
- F02 will consume only `foresight_aggregates`.

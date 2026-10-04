# 2026-10-04 - F02 - synthetic scenario rehearsal

| Field | Value |
|---|---|
| Author(s) | agent: Codex wrote the code, tests and this entry |
| Work package | F02 |
| PR / commit | not committed |
| Units touched | foresight, HTTP demo interface |

## What changed

- Added seeded aggregate segment-persona rehearsal behind an interface.
- Added baseline-vs-swarm band comparison and core change-type coverage.
- Added seed, implementation version, synthetic provenance and calibration
  warnings to the Desk-facing response.

## Why

F02 requires a prototype-safe swarm concept alongside the existing baseline,
without introducing a vendor dependency or individual customer simulation.

## Decisions made

- The implementation is internal, deterministic and dependency-free.
- Synthetic backtests never open the existing real-launch calibration gate.

## Docs updated

- [x] Foresight MODULE.md and CHANGELOG.md

## Tests

- Focused Foresight and route selection: 64 passed.
- `make check`: Ruff and formatting clean; mypy strict clean across 219 source
  files; 3 import contracts kept; 2,005 passed, 544 skipped in 51.95s.

## Open issues / next step

- UI02 will render the comparison and warnings as dedicated workspaces.

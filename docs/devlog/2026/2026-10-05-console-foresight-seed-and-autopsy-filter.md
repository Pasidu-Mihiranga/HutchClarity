# 2026-10-05 - console - foresight seed and autopsy filter

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | R5 frontend, foresight seed |
| PR / commit | uncommitted |
| Units touched | app, foresight, console |

## What changed
- A fresh synthetic world stores two labelled scenarios (a pack retirement and a price increase) and one rehearsal of each. `foresight_seed.py` is what drafts them. The composition root calls it when no scenario is stored yet.
- Complaint Autopsy can be searched by cluster name, suggested rule, or status label, and filtered to hypothesis, confirmed, or rejected.

## Why
The rehearsal page had no stored scenario, so it read as an empty product. The autopsy list is long enough that finding one cluster meant scrolling the whole set.

## Decisions made
- Calibration is not seeded. There is no real launch record, and a backtest invented here would look like a measurement.
- The early-warning radar is left to its own counts. A spike is not written by the seed.
- The filter uses status and the text already on a cluster. It does not add a new category.

## Docs updated
- [x] MODULE.md of: foresight
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
`tests/unit/test_foresight_seed.py`: two scenarios, both rehearsals succeeded, a second call drafts nothing.

## Open issues / next step
The lite profile keeps this in memory, so it is present after the API process starts and gone when that process stops.

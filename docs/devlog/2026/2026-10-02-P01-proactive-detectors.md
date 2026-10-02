# 2026-10-02 - P01 - Proactive stream detectors

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | P01 (#41), R6 |
| PR / commit | uncommitted |
| Units touched | proactive, app composition, policy, persistence collections |

## What changed

- Added idempotent consumers for payment, usage threshold and pack expiry facts.
- Added policy-backed duplicate reload, FUP 80/95 and pack-end detection.
- Published `risk.detected@v1` in the risk record's unit of work.
- Routed duplicate-reload risks into one zero-contact AUTO_FIX case.
- Guarded the event delivery loop against nested consumption of its queue head.

## Why

Issue P01 requires evidence-fed proactive detection and an acceptance path where
two payment captures with one credit are fixed without human input.

## Decisions made

- Proactive only recognizes and records risks. The existing resolution service
  remains responsible for cause detection, policy decisions and actions.
- FUP warning percentages and the duplicate window remain policy artefacts.
- Pack expiry publishes a risk fact but does not execute an action.

## Docs updated

- [x] proactive `MODULE.md`
- [x] `docs/modules.md`, `ARCHITECTURE.md`
- [x] `CHANGELOG.md`, plan 21 status and plan revision record
- [ ] Walkthrough: no existing user-visible walkthrough changed

## Tests

- Targeted proactive unit and zero-contact acceptance tests: passed.
- `ruff` and strict `mypy` on the changed Python surface: passed.
- `make check`: 1,222 passed, 512 infrastructure-dependent skipped; lint,
  formatting, strict typing across 193 source files and all three import
  contracts passed.

## Open issues / next step

Production source mappings and risk parameters require HUTCH confirmation.
The other Wave 4 tracks remain separate work packages.

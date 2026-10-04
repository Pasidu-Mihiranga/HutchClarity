# 2026-10-04 - SIM - Synthetic subscribers use the Hutch 078 prefix

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | hutch-sim data (no plan step) |
| PR / commit | branch `fix/sim-hutch-078-numbers`, no PR yet |
| Units touched | `integration.drivers.mock`, `interfaces.http` (demo data), `kernel` (docstrings), scripts, tests, e2e, console and customer-web defaults, WT-02 |

## What changed
- The five synthetic MSISDNs moved from the 077 prefix to Hutch's 078 prefix:
  `+94771234567` to `+94781234567` (Dilani), `+94772223333` to `+94782223333` (Nimal),
  `+94773334444` to `+94783334444` (Kumar), `+94774445555` to `+94784445555` (Priya),
  `+94770000000` to `+94780000000`.
- Every written form moved with them: `0771234567`, `%2B94771234567`, `+94 77 123 4567`, `077-123-4567`.
- The leak assertions (`"771234567" not in ...` in receipts, logs, tokens, traces, case and channel tests) now check `781234567`. Left alone they would still pass, but test nothing.

## Why
077 is not a Hutch prefix, and the deck's own example uses `078 123 4567` (I21: the deck wins).

## Decisions made
- Unchanged on purpose: `+1771234567` in `test_schemas.py` (an invalid, non-Sri-Lankan input) and `0712345678` in `test_pii_languages.py` (a masking input for a different operator).
- **ASSUMPTION:** 078 is a Hutch prefix (per the deck). The numbers stay synthetic and labelled `hutch-sim`. Because they now use a live Hutch range, they may belong to real subscribers, so they must never reach a real SMS or WhatsApp provider. Today they cannot: every channel driver in the repository is simulated.

## Docs updated
- [x] Walkthrough WT-02 (demo subscriber number)
- [ ] CHANGELOG.md / contracts: no `/v1` shape change, only synthetic data values

## Tests
- Backend: full `pytest` on the branch, exit 0 (infrastructure tests skipped as usual).
- `ruff check` and `ruff format --check` on the changed Python files: clean.

## Open issues / next step
- In-flight branches that hard-code `+9477...` (the WhatsApp channel work) need the same rename when they rebase.

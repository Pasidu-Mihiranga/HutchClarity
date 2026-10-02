# 2026-10-02 - M-DEC - ZEN decision table

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | M-DEC (#36), R3 |
| PR / commit | uncommitted |
| Units touched | decision, policy artefacts, resolution |

## What changed

- Added the versioned GoRules ZEN-compatible decision table and loader.
- Wired production decisions to the table and published `decision.generated@v1`.
- Added canonical and 1,000 generated-input parity checks against the reference Python policy.

## Why

ADR-0026 makes outcome policy reviewable data while retaining deterministic rules as the decision authority.

## Decisions made

- The Python policy remains the executable parity oracle during migration.

## Docs updated

- [x] decision `MODULE.md`
- [x] `ARCHITECTURE.md` / `docs/modules.md`

## Tests

Decision parity and governance preview tests passed.

## Open issues / next step

None in this work package.

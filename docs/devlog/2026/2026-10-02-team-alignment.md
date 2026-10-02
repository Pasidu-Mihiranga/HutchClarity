# 2026-10 - Alignment with combined enterprise plan

> **Merged 2026-10-02:** imported from the team's `main` into the `dev` branch; paths updated to the R1 layout (see `2026-10-02-R1-dev-merge.md`).

| Field | Value |
|---|---|
| Date | 2026-10-02 |
| Work package | docs consolidation |
| Author | Thanoj Buddhima |

## What changed

- Deleted the side folder `HutchClarity-new/`.
- Made [`docs/enterprise-plan/`](../../enterprise-plan/README.md) the single combined plan (chapters 01–19 + CHANGES).
- Installed ADR-0001…0014 as the canonical set; moved older ADRs to [`docs/adr/legacy/`](../../adr/README.md).
- Promoted living docs (`AGENTS.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `SECURITY.md`) to the repo root from the combined version (paths retargeted to `docs/enterprise-plan/`).

## Next

Keep `ARCHITECTURE.md` status rows in sync as modules move from planned to built.

# 2026-10-04 - CD01 - A superseded commit is skipped, not failed

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | CD01 #58 |
| PR / commit | branch `fix/cd-superseded-release` |
| Units touched | `.github/workflows/deploy-vps.yml` |

## What changed
- After CI, a `workflow_run` deploy for a commit that is no longer the head of `main` ends with a notice and deploys nothing (`operation=skip`); the newer commit's own run deploys.
- A manual deploy may name any CI-approved commit that is on `main` (`compare <sha>...main` is `identical` or `ahead`). Before, it had to be the head.

## Why
Merging #64 and #65 (and later #67 and #66) seconds apart started two CI runs. The older commit's deploy reached the "head of main" guard after `main` had moved and failed (runs 37184172796, 37185289321), so the pipeline looked broken when the newer commit had deployed fine.

## Decisions made
- The guard still refuses commits that are not on `main` and commits without a successful CI run.

## Docs updated
- [ ] None

## Tests
- `compare` semantics checked on the live repository: an older commit on `main` reports `ahead`, the head reports `identical`.
- YAML parses. The live proof is the run this merge triggers.

## Open issues / next step
- None.

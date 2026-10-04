# 2026-10-04 - AU02 - Autopsy dataset hardening

| Field | Value |
|---|---|
| Author(s) | agent: Codex wrote the code, tests and this entry |
| Work package | AU02 |
| PR / commit | not committed |
| Units touched | autopsy, HTTP demo interface |

## What changed

- Added mask-first batch ingestion for DATA01 through `AutopsyService.accept`.
- Added reviewer workspace metadata: masked examples, language counts,
  synthetic trends, mapping labels and active-method disclosure.
- Replaced the tiny demo tuple with the DATA01 corpus.

## Why

AU02 requires a meaningful synthetic clustering demonstration while preserving
the existing pipeline, review workflow and repository boundaries.

## Decisions made

- The offline method remains `TrigramSimilarity`; the API explicitly says it
  is not semantic embedding clustering.
- This issue does not activate rules. Suggested mappings remain hypotheses.

## Docs updated

- [x] Autopsy MODULE.md and CHANGELOG.md
- [ ] OpenAPI snapshot: response remains the existing untyped object contract

## Tests

- Focused Autopsy suite: 63 passed.
- Route contract subset: 3 passed.
- `make check`: Ruff and formatting clean; mypy strict clean across 218 source
  files; 3 import contracts kept; 2,002 passed, 544 skipped in 51.56s.

## Open issues / next step

- A vector-capable `embed` role is still required before an honest embedding
  provider can replace the deterministic fallback.

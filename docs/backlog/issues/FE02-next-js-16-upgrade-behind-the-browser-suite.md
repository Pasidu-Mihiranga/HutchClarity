# [FE02] Next.js 16 upgrade, gated on the browser suite

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `frontend` |
| Priority | P3 |
| Depends on | [FE01](FE01-frontend-verified-build-static-ui-retired-next-j.md) |
| Plan | 19 §2.2 |
| Labels | `wave:w5`, `area:frontend`, `priority:p3`, `type:chore` |

## Context

Plan 19 names Next.js 16; the three apps run on 14.2.35. FE01 attempted the
upgrade and reverted it: 16.3.8 installs cleanly, keeps React 18.2, passes
`tsc --noEmit` and builds all three apps, and then fails 7 of the 9 browser
tests that pass on 14. `allowedDevOrigins`, the migration note Next prints for
the blocked `/_next/hmr` requests, changed which tests failed without reducing
how many. ADR-0031 records the decision to stay on 14 until this is resolved.

Nothing in the failures pointed at a defect in our code; they are runtime
differences between the two majors that need their own investigation. That is
this issue.

## Scope

- Diagnose the 7 browser failures on Next.js 16 (chat journey, knowledge
  citation, no-source handoff, sign-in, and the four axe audits)
- Upgrade the three apps and the lockfile once the suite passes
- Two traps FE01 hit: 16 rewrites `tsconfig.json` and `next-env.d.ts` in every
  app on install, so a revert has to restore those too; and it writes
  `AGENTS.md` and `CLAUDE.md` into `apps/customer-web/`, which by the
  "closest file wins" rule would put a dependency's agent instructions above
  this repository's own for anyone working in that directory. Neither may be
  committed by accident.
- Supersede ADR-0031 rather than editing it

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the three apps on Next.js 16 | `make web-build` | all three build | `frontend` CI job |
| 2 | the three apps on Next.js 16 | `make e2e` | the whole browser suite passes, with no test skipped or relaxed | `frontend e2e` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

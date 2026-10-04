# [FE01] Frontend: verified build, static UI retired, Next.js 14, accessibility and language review

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `frontend` |
| Priority | P1 |
| Depends on | [B09](B09-frontend-sdk-generated-from-openapi-checked-in-c.md) |
| Plan | 19 §2.2 |
| Labels | `wave:w5`, `area:frontend`, `priority:p1`, `type:feature` |

## Context
Next.js 14 apps; build not verified on dev; static UI still served.

## Scope
- Green build in CI (blocking); retire `interfaces/http/static` once parity is shown
- axe checks; native-speaker review of si/ta strings
- **Next.js 14 is the framework** (ADR-0031). This issue said "upgrade to
  Next.js 16"; the upgrade was attempted here and reverted, because 16.3.8
  builds and then fails 7 of the 9 browser tests that pass on 14. It is
  [FE02](FE02-next-js-16-upgrade-behind-the-browser-suite.md) now, with the
  browser suite as its gate rather than the build.

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | the four journeys | driven in the Next.js apps | pass in Playwright | `frontend e2e` |
| 2 | each page | axe run | no serious violations | `frontend e2e` |
| 3 | the Desk's queue and a four-eyes approval | driven in the console app | the case the agent raised is approved by a stepped-up supervisor and ends at a verified receipt | `frontend e2e` |
| 4 | a receipt number that was never issued | opened on the public verify page | the page says so, and reports neither a valid nor an invalid chain | `frontend e2e` |

## Definition of Done
- [x] Every acceptance test above exists, fails before the change and passes after it
- [x] `make check`: lint, format, `mypy --strict`, import contracts, module boundaries and dependency map all pass; 1985 tests pass. One test fails in the container this ran in for an environmental reason (`test_an_outbound_connection_is_refused`: the container's outbound proxy answers before the repository's own network guard can raise). It fails identically on the unmodified base commit, so **CI confirms this row**.
- [x] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [x] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [x] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [x] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1

## Outcome

Acceptance tests 3 and 4 were added here. Tests 1 and 2 existed from C05 but
had never been executed, because the browser could not be downloaded in the
environment that wrote them; they ran green for the first time in this change.

Retiring the static UI needed parity evidence for all three of its pages, and
the suite covered only customer-web, so the console Desk and the public verify
page got the two new tests. Writing test 4 found a real defect: the verify page
fell back to a "placeholder" verdict whenever the API call failed, and that
verdict was *valid* for any id not containing the string "bad". An unknown
receipt rendered a green "Chain valid" with "Signature OK". The static page it
replaces showed an error on a 404, so this was a regression on the one page
whose whole job is to prove a receipt is genuine. Fixed: three outcomes, and
"could not check" is one of them.

The si/ta strings were reviewed by a native speaker and the result was
accepted (reported by the maintainer, 2026-10-04).

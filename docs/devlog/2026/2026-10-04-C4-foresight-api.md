# 2026-10-04 - C4 (F06) - a real foresight API, and who may call it

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code, for Pasidu Mihiranga |
| Work package | C4 (workstream C, plan item F06) |
| PR / commit | branch `feat/foresight-api`, stacked on C2 with C3 merged in |
| Units touched | platform/security, interfaces/http, config/opa, docs/enterprise-plan |

## What changed

- **Fourteen `/v1/foresight` routes**: draft and revise scenarios, list and read them, request a run (202 with a `Location` poll URL), list and poll runs, record a launch and its outcomes, run and list backtests, read the latest calibration, list spikes.
- **Four permissions**: `foresight:read`, `foresight:scenario:draft`, `foresight:run`, `foresight:outcome:record`.
- **A new `Role.PRODUCT`**, holding the first three and **not** the fourth. `Role.CX_ENGINEER` gained `foresight:read` and `foresight:outcome:record`.
- `config/opa/data.json` updated to match, so the Rego and the Python driver stay in parity.
- Request schemas in `interfaces/http/schemas.py`; view helpers in `main.py`.
- OpenAPI golden, `contracts/openapi.json` and the frontend SDK types regenerated.
- `tests/acceptance/test_route_contract.py`: all fourteen routes classified `SIGNED_IN`.
- **Plan 10 §250 fixed**, plus `CHANGES.md` v1.13 and the README revision table.

## Why

Plan C4 asks for the API, the permissions and the new role, and names two things to fix on the way.

**The path.** Plan 10 §250 said `POST /v1/simulation/scenarios`. Everything else, including the module, says foresight. Chapter 10 is a chapter 01-17 document and therefore lowest precedence (AGENTS.md §1), so the plan is what changed. A test asserts no `/v1/simulation` path exists, so the contradiction cannot come back quietly.

**The role.** `config/policy/proactive.yaml` already wrote `owner_role: product` with no matching `Role` member, and C1 added `config/policy/foresight.yaml` doing the same. A policy key owned by a role that does not exist is a key nobody can be held to. `Role.PRODUCT` now exists.

## Decisions made

- **`PRODUCT` does not get `foresight:outcome:record`.** This is the plan's instruction and it is worth restating why: recorded outcomes are the only thing that can move a backtest to `CALIBRATED`, and product is the role that wants the gate open. The same maker-checker split the money path uses, applied to evidence instead of to a refund. Two acceptance tests pin it from both sides: product is refused the launch route, CX is refused the drafting route.
- **`Idempotency-Key` is a required header, not an optional one** (I8). FastAPI returns 422 without it. Foresight moves no money, so the risk is not a double charge; it is a double finding, and two runs of one scenario reported twice is how a rehearsal gets counted as two pieces of evidence. A repeat returns the original run with `replayed: true` so a caller can tell.
- **The run executes inline behind the 202.** The rehearsal is milliseconds of arithmetic, and a queue the prototype has no worker for would leave every run `queued` forever. The 202 and the poll URL are the contract a serverless batch job keeps when plan 21 moves foresight (R6/R7), so a caller written today does not change when it does.
- **`GET /v1/foresight/calibration` is a 404 before any backtest has run**, not a cheerful "not calibrated". The two are different and only one of them has been measured.
- **An unknown change type is a 422**, not a run that predicts nothing. "No themes configured for this type" and "you named a type that does not exist" look identical on screen and are not the same problem.
- **A real launch is a 403** with the reason in the body, carrying C2's refusal through to the API rather than letting the route open a path the service closes.
- **Every route is `SIGNED_IN`, none public.** A rehearsal names changes HUTCH has not announced; the predictions are about customers in aggregate but the *scenario* is commercially sensitive.
- **The view helpers compute nothing.** A view that did arithmetic would be a second place a band could be decided, and banding belongs to the module under policy thresholds (ADR-0043). `None` is rendered as `null` throughout: a `0.000` error over zero compared pairs would read as a flawless model.

## Docs updated

- [x] `MODULE.md` of: foresight (used-by, the `/v1` surface table with permissions, invariants, tests, history)
- [x] This devlog
- [x] `CHANGELOG.md`
- [x] **`/v1` contract change**: OpenAPI golden regenerated with `UPDATE_GOLDEN=1`, `make contracts` re-exported `contracts/openapi.json` and regenerated the SDK types, `make contracts-check` passes
- [x] **Plan**: 10 §250 corrected, `docs/enterprise-plan/CHANGES.md` v1.13, README version and revision table
- [ ] ADR: none. C4 implements decisions the plan already records; the duty split follows the existing separation-of-duties pattern rather than introducing one.
- [ ] `docs/modules.md` / `ARCHITECTURE.md`: not needed. No new module, no new dependency between modules.
- [ ] Walkthrough: not needed yet. No console screen reads these routes; the demo route still backs the Foresight page, and retiring it is D4's job.

## Tests

- `tests/acceptance/test_foresight_api.py`: **42 new tests**. The path choice, deny-by-default on all fourteen routes, the duty split from both sides, scenario versioning, the 202 and poll URL, idempotency including a repeat after the run finished, unknown change type and band, the 404s, and that a synthetic backtest never claims calibration.
- `tests/acceptance/test_route_contract.py`: extended, so an unclassified route still fails the build.
- `make check`: **2935 passed, 782 skipped**, ruff, mypy --strict over 250 files, import contracts 3 kept 0 broken.
- `make contracts-check`: SDK types match the committed schema. `npm run typecheck` in `frontend/`: clean.

**Not verified locally:** the real-Rego parity lane. `tests/contract/test_authz_parity.py` runs its Python stand-in over the same `config/opa/data.json` and passes, but the lane that queries a real OPA needs `CLARITY_OPA_URL`, and this environment has no OPA binary and no egress to fetch one. CI's `backend full` job runs it. The Rego itself is generic over `data.clarity.role_permissions[role]`, so adding a role is a data change rather than a policy change, which is why the stand-in is meaningful here.

## Open issues / next step

- C5 fills `GET /v1/foresight/spikes`; the route returns an empty list until then.
- C6 replaces the 403 on a real launch with the capability and evidence checks, and adds the metrics.
- No console screen reads these routes yet. D4 retires `GET /v1/demo/foresight` once one does; until then both exist and the demo route is the one the Foresight page uses.
- `POST /v1/foresight/backtests` recomputes over every stored launch each time. That is right at these volumes and would want a cursor if the launch table ever grew.

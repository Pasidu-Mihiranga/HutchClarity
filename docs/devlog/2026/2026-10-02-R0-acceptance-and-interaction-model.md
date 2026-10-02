# 2026-10-02 - R0 - Acceptance suite, route audit and module interaction model

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Anthropic), working with the team lead |
| Work package | R0 and the interaction design (docs/enterprise-plan/21 §7, §11) |
| PR / commit | branch `feat/r0-interaction-model` from `main` (`89e3529`) |
| Units touched | tests/acceptance (new), tests/architecture, interfaces.http, docs |

## What changed
- R0 acceptance suite (black-box over HTTP): route contract classifying all 66 routes as public, signed-in or synthetic-only; the four journeys plus subject binding and MCP; OpenAPI snapshot of 54 operations and 35 schemas
- Route audit found D7: seven `/mock/*` simulated-HUTCH routes had no sign-in and no profile guard; now `demo_only` (404 in `prod`)
- Route audit found D8: the ten `/v1/me/*` routes were authorised by `case:read` for everything, including money-moving self-care; now three named permissions held only by customers (`self:read`, `self:settings`, `self:transact`), staff get 403
- Module dependency map declared and enforced, with a cycle check (`tests/architecture/test_module_dependencies.py`)
- ADR-0029 and plan 21 §11: calls for answers, outbox events for side effects; event catalogue; delivery rules; first event-driven flow (receipts on `action.completed`); R2a platform work packages
- AGENTS.md I22 and sync-matrix rows for dependencies, events and the `/v1` snapshot

## Decisions made
- A dependency audit by pattern produced one false alarm (`GET /v1/admin/switches` checks permissions inside the handler); the route contract test now records actual behaviour instead

## Tests
- `make check`: ruff, ruff format, mypy --strict (106 files), 3 import contracts, 546 passed (84 acceptance, 6 architecture)

## Open issues / next step
- R2a.1-R2a.4 (event contracts, unit of work and repositories, bus drivers, outbox and consumers), then the receipts flow (21 §11.5)
- (fixed in the same change, D8) `/v1/me/*` now declare `self:read`, `self:settings` or `self:transact`

# 2026-10-02 - R1 - Restructure into the target layout, fix D1-D4 and D6, merge docs

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Anthropic), working with the team lead |
| Work package | R1 and R0.5 (docs/enterprise-plan/21 §7) |
| PR / commit | not yet committed |
| Units touched | whole backend (moved), all modules, docs |

## What changed
- Backend moved to `backend/`; layers `kernel → contracts → integration → platform → ai → modules → app → interfaces → entrypoints`, enforced by 3 import contracts
- `public.py` per module; outside code imports only that (architecture test); `modules.actions` split into `public` (vocabulary) and `capability` (money-moving, `case` and `app` only)
- `MODULE.md` per module; composition root in `clarity.app`; ASGI entry `clarity.entrypoints.asgi:app`
- MCP server is built by the interface layer from the container's narrow view; HTTP and MCP are independent
- Fixed D1 (one execution and one receipt per plan, replays return the original), D2 (four-eyes threshold from policy), D3 (staff dev sign-in demo-only), D4 (receipts name the approving roles), D6 (Playwright optional extra)
- Plans merged into `docs/enterprise-plan` v1.3 (new chapters 18-21); ADRs merged into one sequence 0001-0028; `AGENTS.md` replaces `agent.md` (history kept in `2026-10-02-HISTORY-agent-md.md`); root Makefile; README, ARCHITECTURE, CONTRIBUTING, SECURITY, CHANGELOG, submission docs updated

## Why
Chapter 21 and ADR-0025: keep the proven logic, rewrite the structure, replace infrastructure step by step. Defects on the money path and identity first.

## Decisions made
- Composition root is its own layer (`app`) below the interfaces, because both HTTP and MCP sit on the assembled core
- A repeated confirm returns `200` with the original receipt instead of `409` (deliberate `/v1` contract change, recorded in CHANGELOG)
- ADRs 0025-0028

## Docs updated
- [x] MODULE.md (all 10 modules), docs/modules.md, ARCHITECTURE.md
- [x] Plan v1.3 (README, CHANGES.md, chapters 03-21), ADR index
- [x] WALKTHROUGHS index, CHANGELOG, submission docs

## Tests
- `make check`: ruff, ruff format, mypy --strict (94 files), 3 import contracts, 447 tests passed
- Stress: 1,500 concurrent double confirms: 1,500 x (one refund, one receipt, no error); before the fix 1,486 duplicate receipts and 8 stuck plans
- Server smoke test from the new entry point: `/health`, `/`, `/desk`, `/docs` return 200

## Open issues / next step
- R0: black-box `/v1` acceptance suite
- D5 and R2 (PostgreSQL, Kafka, Keycloak, OPA drivers in the `full` profile)
- Only one process may run until R3 moves concurrency guarantees into the database

# Changelog

Notable changes to Hutch Clarity. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/). Public-surface and `/v1` contract changes are always listed.

## [Unreleased]

### Added (Wave 1 core modules)

**`/v1` contract change.** Nine new operations; the reviewed OpenAPI snapshot
was regenerated on purpose (`backend/tests/acceptance/golden/openapi-contract.json`).
No existing operation changed shape, so a current client keeps working.

- Policy Studio (M-GOV, #20): `GET /v1/admin/policy/changes`, `POST /v1/admin/policy/changes`, and `review`, `approve`, `schedule`, `activate`, `rollback` on `/v1/admin/policy/changes/{change_id}`. Staff only; separation of duties is enforced by the governance gate, not the route, because a route cannot know who drafted a change.
- `POST /v1/auth/refresh` (M-IAM, #7): exchanges a refresh token for a new access token. Public, like sign-in: the refresh token is the credential.
- `GET /v1/finance/reconciliation` (M-REC, #38): the queue of executed actions with no adapter confirmation. Staff only, because it lists money that moved unmatched.

- Durable idempotency, transient-versus-final refusals, durable confirmation tokens, and `approval.requested@v1` (M-ACT, #25).
- Orchestration split out of `CaseService` into `clarity.modules.resolution`; the aggregate keeps the case and its state machine (M-CASE, #34). Method names unchanged, so the HTTP and MCP interfaces were untouched.
- Rule confidence can come from the policy store, resolved as of the disputed event, and four new rule packs: `VAS_RENEWAL_UNNOTIFIED`, `PACK_MISMATCH`, `LOAN_RECOVERY`, `OUTAGE_DURING_PACK` (M-DET, #35).
- Keycloak JWKS verification, OPA authorization parity, shared OTP state and revocable rotating sessions (M-IAM, #7).
- Persisted Policy Studio lifecycle with approvals, schedules, activations, supersession and rollback drafting (M-GOV, #20).
- GoRules ZEN-compatible outcome table with a 1,000-input reference parity suite (M-DEC, #36).
- OpenBao Transit signing, retained rotation keys, isolated stateless rendering and `receipt.issued@v1` (M-RCPT, #37).
- Daily action reconciliation and `reconciliation.mismatch@v1` (M-REC, #38).

Consumers to update: the frontend SDK is regenerated from the schema (`make contracts`), which is checked in CI.

### Added (B01, #10)
- `clarity.contracts.events`: one typed payload model per catalogued event (17, `type@v1`), a registry, `validate_payload`; a payload class cannot define a personal-data field.
- The event vocabulary moved from `platform.messaging` to `contracts.events` (`EventType` kept as an alias); `Event.of(payload, subject=...)`; `Event.caused(payload)`; `schema_version` is now an integer.
- The outbox validates every event against its schema on `append`.

### Added (R0 and interaction model)
- Acceptance suite `backend/tests/acceptance`: route contract for every route, the four journeys over HTTP, OpenAPI snapshot of the `/v1` contract (regenerate with `UPDATE_GOLDEN=1`).
- Declared module dependency map with a cycle check (`tests/architecture/test_module_dependencies.py`); ADR-0029 and plan 21 §11 (calls for answers, events for side effects, event catalogue).

### Fixed
- D7: the `/mock/*` simulated-HUTCH routes had no sign-in and no profile guard; they now return 404 in `prod`.
- D8: `/v1/me/*` routes were authorised by `case:read` for every action, including reload and pack purchase; they now declare `self:read`, `self:settings` or `self:transact` (customers only; staff get 403).

### Merged from `main` into `dev` (2026-10-02)
- Team commits `74fa3d1`, `2bd8fc9`, `429f035` ported into the R1 layout with 3-way merges: chat module (`modules.conversation`), admin and console APIs, receipt verification and UI updates, synthetic world in SQL for the `full` profile (`integration/drivers/mock/store`), new scripts (`keys`, `seed`, `token_report`, `tag_baseline`).
- Next.js apps and packages in `frontend/` kept (R5 started early).
- The parallel backend from `aeaab67` was not adopted (41 tests, missing the policy resolver and governance); it stays in git history for R2/R4/R6 reference.
- `CLARITY_PROFILE=lite` is accepted as the documented name of `demo`.
- Development identity routes follow the team's rule: allowed in synthetic profiles (`demo`, `full`), 404 in `prod`.

### Changed
- **Repository restructured (migration step R1):** backend moved to `backend/` and layered as `kernel → contracts → integration → platform → ai → modules → app → interfaces → entrypoints`; each module has a `public.py` (only import surface, test-enforced) and a `MODULE.md`; `modules.actions` split into `public` (vocabulary) and `capability` (money-moving code).
- ASGI entry point is now `clarity.entrypoints.asgi:app` (was `clarity.api.main:app`).
- **`/v1` contract:** repeating `POST /v1/cases/{id}/confirm` (or approve, auto-fix) for an executed plan now returns the original result and receipt with `200`, instead of `409 PLAN_NOT_PENDING`.
- Receipts record the roles that actually approved (for example `finance`, or `supervisor+finance` for four-eyes) instead of always `supervisor`.
- Docs merged: one plan (v1.3) with chapters 18-21, one ADR sequence (0001-0028), `AGENTS.md` replaces `agent.md`.

### Fixed
- D1: a concurrent double confirm could issue two signed receipts for one refund, or leave the plan unexecutable; a second confirm after success returned an error.
- D2: the four-eyes threshold in policy was not enforced by the tool layer (a hard-coded LKR 25,000 was used).
- D3: the development staff sign-in had no profile guard; it is now refused in `prod` like the OTP inbox (synthetic `demo` and `full` profiles keep it).
- D6: `make check` failed on a clean clone (Playwright is now an optional `render` extra).

### Added
- Plan chapter 21 (migration, runtime model: containers for the core, serverless at the edges, microservice extraction path) and ADRs 0025-0028.
- Architecture tests for module boundaries; regression tests for D1-D4.

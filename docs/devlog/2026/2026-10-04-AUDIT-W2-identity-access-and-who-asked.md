# 2026-10-04 - Audit assurance W2 - Identity, access, and who asked

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code |
| Work package | `docs/audit-assurance-plan.md` Phase 1, W2 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | interfaces.http (main, new `trail.py`), platform.audit (event types) |

## What changed

- Identity events: `otp.requested` (outcome `sent`, `refused` or
  `unknown_number`), `otp.verified`, `otp.failed`, `staff.session_started`,
  `token.refreshed`, `token.rejected`.
- `access.denied` for every 403, from one exception handler that then answers
  with FastAPI's default handler, so responses do not change. 401s are recorded
  only when a token was presented.
- `request.performed` for every state-changing request: principal, session,
  route template, case and status.
- `session_ref`: a truncated SHA-256 of the access token.
- `tests/security/test_audit_coverage.py`: the coverage contract and the
  identity tests.

## Why

Plan gaps G3 and G4. And one found while building: `action.completed` carries
`confirmed_by` as a mode (`staff_approved`), never the person, so W1's domain
events recorded an approval as done by `clarity`. Only the HTTP layer knows who
asked.

## Decisions made

- **Opt-out, not opt-in.** Every state-changing route is recorded unless listed
  in `NOT_RECORDED_AS_REQUESTS` with a reason (sign-in routes, recorded their
  own way, and three POSTs that only read). Forgetting is impossible by
  default; the contract catches stale exemptions, and every recorded route is
  driven by a test.
- **`request.performed` is not fail closed.** It is written after the handler
  commits, so a failed append turns the response into an error but cannot undo
  the change. The domain events remain the atomic record of what happened;
  this one adds who asked. Recorded in the plan.
- **Nothing secret or personal.** No MSISDN (pseudonym, or mask for unknown
  numbers), no OTP code, no token. A test serialises the whole trail after a
  sign-in and asserts no form of the number appears.
- **Anonymous 401s are not recorded**: they are the normal state of a public
  endpoint and would bury real signals.

## Docs updated

- [x] CHANGELOG.md: Added (W2)
- [x] `docs/audit-assurance-plan.md`: revision 4, W2 ticked, acceptance row 7
- [ ] MODULE.md / ARCHITECTURE.md: no structural change
- [ ] `/v1` contract: unchanged, confirmed by `make contracts-check`

## Tests

- `make check`: lint and format clean, `mypy --strict` clean (217 files),
  contracts 3 kept 0 broken; **`1 failed, 2046 passed, 544 skipped`**. The
  failure is the container-proxy `test_an_outbound_connection_is_refused`,
  unchanged and green in CI.
- `test_audit_coverage.py`: 33 tests, 23 of them one per recorded route,
  each driven as a signed-in agent and asserted to leave a record naming the
  route and the agent.

## Open issues / next step

- Phase 2: signed checkpoints with a dedicated key, receipt cross-anchor,
  public checkpoint endpoint, incremental verification, keyed payload hashes.
- Database-level append-only (W1, still open).

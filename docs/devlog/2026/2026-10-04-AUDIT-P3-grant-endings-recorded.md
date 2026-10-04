# 2026-10-04 - Audit assurance Phase 3 - Grant endings recorded when they happen

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code |
| Work package | `docs/audit-assurance-plan.md` Phase 3, ADR-0036 (amended) |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | modules.iam (grants), interfaces.http (lifespan), app, platform.audit, config/policy |

## What changed

- `AuditGrants.record_endings()` writes `grant.expired` or `grant.lapsed` for
  every active grant whose end has passed, once.
- A sweep loop in each API process, started by the FastAPI lifespan, on
  `audit.grant.sweep_interval` (PT1M).
- `apply()`, which runs on every authenticated request, records endings first.

## Why

The maintainer asked for it. Phase 3 left endings visible only from stored
times, because nothing in the system ran on a timer.

## Decisions made

- **The exact moment, not the moment noticed.** `occurred_at` is the grant's
  `expires_at` or `review_by`; `recorded_at` is when the sweep found it. The
  ledger already kept the two apart (ADR-0033), so a late sweep still states
  the true end, and only `recorded_at` has to be non-decreasing.
- **Lapse versus expiry** is whichever came first: a missed recertification
  before expiry is a lapse.
- **Once across processes.** The ending is claimed by writing `ended_at` in a
  unit of work that read the grant first; a racing process gets
  `ConcurrentUpdate` and records nothing. Claim first, then append; a failed
  append releases the claim for the next sweep.
- **No new infrastructure.** A lifespan task, not a scheduler service. Tests
  build apps with plain `TestClient(app)`, which does not run the lifespan, so
  they start no loops; one test runs it deliberately.
- **A failed sweep never stops the server**: it is logged and retried.
- ADR-0036's consequence amended in place with a dated note rather than
  superseded: the decision did not change, a gap it recorded was closed.

## Docs updated

- [x] ADR-0036 (amended), plan, CHANGELOG, iam `MODULE.md`
- [ ] `/v1` contract: unchanged, confirmed by `make contracts-check`

## Tests

- `make check`: lint, format and `mypy --strict` clean (219 files), contracts
  3 kept 0 broken; **`1 failed, 2165 passed, 604 skipped`**. The failure is
  the container-proxy test, unchanged.
- 10 new tests: the exact end time when noticed two days late, lapse versus
  expiry, once only, two processes on one store, revoked and live grants not
  recorded, a failed append releasing its claim, break-glass endings, the
  per-request trigger, the background sweep under a real lifespan with no
  requests made, and the interval coming from policy.

## Open issues / next step

- Phase 4: risk rules, alerts and their lifecycle, liveness, the chain-break
  playbook.

# 2026-10-04 - AUDIT Phase 5 - the console Audit section

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Opus), for Thanoj Buddhima |
| Work package | Audit assurance plan, Phase 5 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | interfaces.http, app.container, frontend (console app, SDK), contracts, e2e |

## What changed

- **`frontend/apps/console/app/audit/page.tsx`**: all eight panels from plan 5.8.
- **Three `/v1` routes**: `GET /v1/audit/health`, `GET /v1/audit/recovery`,
  `POST /v1/audit/records/{seq}/verify`.
- **`Clarity.now()`** and **`Clarity.pending_event_count()`** on the container.
- **SDK**: nine audit methods and eight exported types.
- **`frontend/e2e/audit-console.spec.ts`**: 9 tests, green.
- The admin page's "Audit trail API: not wired" badge is now accurate.
- WT-15, and the plan's last two Phase 5 items checked off.

## Why

`docs/audit-assurance-plan.md` section 5.8 and Phase 5. The backend has had the
whole audit system since this morning and nothing in the product showed it; the
admin page said so in as many words.

## Decisions made

- **Health polls, the trail does not.** `GET /v1/audit/health` is deliberately not
  recorded as `audit.read`. A dashboard polling it would trip `mass_audit_read`
  within minutes, so the monitor would raise alerts about the act of monitoring.
  It reads aggregates and a verdict, never record contents, so there is nothing
  about a person in it. The trail explorer loads on a button press, and its read
  *is* recorded, which a browser test asserts by counting `audit.read` records
  before and after.
- **Health verifies incrementally**, for the same reason: a full recompute on
  every poll makes the dashboard the most expensive thing in the system. The panel
  prints what that does and does not cover rather than letting a green badge imply
  more than it proves.
- **No backup, restore, archive, hold or erase buttons.** Those need step-up and,
  for a restore, an authority that is not grantable. They belong in the runbook
  (WT-14), not in a console a desk supervisor can open.
- **Shift handover is not built.** Plan 5.8 lists it under Monitors. There is no
  shift model in the system, so the panel shows duty start times and alert
  ownership, which is what the trail actually knows. Said in WT-15 rather than
  left as an implied gap.
- **"Verify this record" recomputes hashes, not payloads.** `proves()` needs the
  document the caller holds, which a console does not have. The route's docstring
  and the walkthrough both say so, because a button labelled "verify" that
  quietly verified less than a reader assumes is worse than no button.

## Things found while doing it

- **One panel's refusal blanked the whole page.** The first browser run showed
  `GET /v1/audit/grants` answering 403 for Compliance, which holds `audit:read`
  and `alert:dispose` but not `audit:assign`. A single `Promise.all` turned that
  expected refusal into an empty page with an error banner. Deny by default means
  different roles legitimately see different panels, so each panel now loads on
  its own and a 403 reads as *not for this role*. A test pins it.
- **I first detected the 403 by matching the error message text.** Wrong: the SDK
  already carries a typed `status` on `ClarityApiError`, and matching on wording
  breaks the moment a detail string changes. Fixed to read the status.
- The role picker's labels are `Security` and `Platform`, not `Security Admin`;
  the first draft of the spec used the long names and could not sign in.

## Docs updated
- [x] Walkthrough WT-15, indexed in `docs/WALKTHROUGHS.md`
- [x] `CHANGELOG.md`: the three routes, the SDK methods, the console section
- [x] `docs/audit-assurance-plan.md` Phase 5 checked off, revision 11
- [x] `contracts/openapi.json`, the golden snapshot and the frontend SDK
- [x] `backend/src/clarity/interfaces/http/trail.py`: the verify route is listed
      in `NOT_RECORDED_AS_REQUESTS` with its reason (POST, but read only)
- [ ] MODULE.md (no module changed; the routes read existing services)

## Tests

`make check`: **1 failed, 2361 passed, 625 skipped**, the failure being the
pre-existing `test_an_outbound_connection_is_refused` (403 from this container's
egress proxy; passes in CI). `make contracts-check`: passes.

Browser: `audit-console.spec.ts` 9 of 9, whole suite **28 of 28** (was 14 before
the audit work). Run against the installed Chromium 1194 via a local config that
is deleted before every commit, because the pinned Playwright wants 1243 and
downloading is blocked in this container.

## Open issues / next step

Every phase of the plan has landed. Two items remain open with stated reasons:

- **Database-level append-only.** Needs an insert-only write path; the generic row
  store uses `INSERT ... ON CONFLICT DO UPDATE`, so revoking UPDATE would break
  every write rather than just an audit rewrite.
- **Cross-anchoring the audit head into the receipt chain.** Changes a signed
  receipt payload, which is a money-path contract change needing two approvals.

Also still outstanding from earlier findings: `GET /v1/cases` does not exist, so
the customer case list renders fabricated rows. Unrelated to audit, and the oldest
item on the list.

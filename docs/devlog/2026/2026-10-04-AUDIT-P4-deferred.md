# 2026-10-04 - AUDIT Phases 2 and 4 deferrals - the items the earlier phases left open

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Opus), for Thanoj Buddhima |
| Work package | Audit assurance plan, Phase 2 and Phase 4 deferrals |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | platform.audit, platform.config, modules.assurance, interfaces.http, app.container, config/policy |

## What changed

- **No keyed payload hash.** The plan's proposed HMAC over `payload_hash` is
  dropped and replaced by `platform/audit/entropy.py`, which screens every
  append and refuses a raw MSISDN, NIC, card number or email in the payload or
  the detail. ADR-0033 carries the reasoning as an amendment.
- **Incremental verification.** `AuditLedger.verify(since=, since_hash=)` and
  `Checkpointer.verify(incremental=True)` recompute only from the newest
  verified checkpoint upward, with the anchor row itself recomputed.
  `ChainVerification` and `CheckpointVerification` gained `verified_from`.
- **`data.read`.** The HTTP middleware now records a staff `GET` on a route
  naming one subject, which is the signal the snooping rule needs.
  `trail.records_data_read` says which reads qualify.
- **Six new risk rules**, completing plan section 5.7: `snooping`, `collusion`,
  `budget_pressure`, `off_hours`, `grant_abuse`, `agent_pressure`. Fourteen
  rules in total, all counted, all with policy-resolved thresholds.
- **Outbox lag.** `trail_lag` counts events committed but never published, and
  the container injects the reader. A stalled relay leaves state changed and the
  trail quiet, which is the exact failure the heartbeat exists for.
- **`SwitchBoard` takes the injected clock** (I11), closing the follow-up
  ADR-0037 recorded. The `switch_then_pay` test no longer passes times by hand.
- **Fifteen new policy keys** in `config/policy/audit.yaml`.

## Why

`docs/audit-assurance-plan.md`, the unchecked items under Phases 2 and 4. The
six scenarios were deferred as "needs a signal the trail does not yet carry, or
a baseline"; all six turned out to be reachable once `data.read` existed and
once working hours were treated as configuration rather than as a baseline.

## Decisions made

- **The keyed hash was the wrong fix and is not being done.** It would have made
  the trail verifiable by Clarity alone, which is the property the design exists
  to avoid, and it would have protected `payload_hash` while leaving `detail`,
  which is stored in the clear, untouched. Refusing the identifier at the door
  is strictly stronger. ADR-0033 amendment.
- **The entropy screen raises rather than scrubbing.** A value that should have
  been masked is a defect at its source, and an append-only store cannot be
  edited afterwards, so the loud failure is the right one. The cost is that a
  false positive fails a real operation, so the patterns need structural signals
  and non-alphanumeric boundaries, and opaque cryptographic fields are listed and
  skipped. Measured at zero false positives over 20000 synthetic hash/signature
  pairs; the whole 2266-test suite exercises the real payload shapes.
- **Incremental verification is a freshness check, not a tamper check.** My first
  version of this claimed the anchor's hash covers every record below it. It does
  not, and a test caught it: editing a record and recomputing only its own hash
  leaves its successors' `prev_hash` untouched, so the anchor hash is unchanged.
  The full recompute stays the default. ADR-0035 amendment, with a test that
  asserts the limitation so nobody reads the parameter as a free upgrade.
- **`off_hours` uses configured hours, not a learned baseline**, because a
  baseline is a model and a model scoring a person's working pattern is a guess
  wearing a number's clothes (I1). Colombo time is a fixed UTC+5:30 offset rather
  than a tzdata lookup, so the rule has no dependency a deployment could be
  missing: **ASSUMPTION**, Sri Lanka has kept UTC+5:30 with no daylight saving
  since 2006.
- **`budget_pressure` does not shadow the refund cap.** `assurance.budget.window_alert_lkr`
  is a compliance-owned figure for how much may move in total before somebody is
  told, which is a different question from the per-case cap the decision policy
  enforces and the per-day cap the budget enforces. Shadowing the cap would have
  broken D2.
- **`data.read` records one subject, not every list.** Recording list requests
  would multiply the trail by the console's polling and answer no question: the
  queue is public to the desk. `records_data_read` carries the reasoning.
- The `collusion` finding names no `subject_ref` when several people approved,
  because naming one would pick a suspect, and the second-person rule would then
  let the other close the alert on themselves.

## Docs updated
- [x] MODULE.md of: `modules/assurance`
- [ ] ARCHITECTURE.md / modules.md (no new module or module edge)
- [ ] Walkthrough (no user-visible flow changed)
- [x] ADR-0033 amendment (no keyed payload hash), ADR-0035 amendment
      (incremental verification and its limits)
- [x] `docs/audit-assurance-plan.md` items checked off
- [ ] Plan via CHANGES.md (no enterprise-plan chapter changed)

## Tests

`make check`: **1 failed, 2266 passed, 604 skipped**. The one failure is
`tests/unit/test_cassettes.py::test_an_outbound_connection_is_refused`, which
asserts an outbound connection is refused and instead gets `403 Forbidden` from
this container's egress proxy. It fails identically on the base commit and passes
in CI; nothing in this change touches it.

`make contracts-check`: passes. `/v1` is unchanged, so the OpenAPI snapshot and
the frontend SDK are untouched.

New tests: `tests/security/test_audit_entropy.py` (25 cases), the incremental
verification tests in `tests/unit/test_audit_checkpoints.py`, and the six
scenarios plus the lag rule and the two policy-contract tests in
`tests/unit/test_assurance.py`.

## Open issues / next step

- The policy-contract test (`test_every_rule_resolves_against_the_real_policy_store`)
  exists because `run` swallows a broken rule by design. That is the right
  trade-off for a live system but it means a rule can fail silently in
  production; the dashboard should surface `<rule>_failed` alerts distinctly.
- Database-level append-only still needs an insert-only write path: the row store
  uses `INSERT ... ON CONFLICT DO UPDATE`, so `REVOKE UPDATE` would break every
  write, not just an audit rewrite. Unchanged from Phase 1.
- Cross-anchoring the audit head into the receipt chain is still open and still
  touches a signed payload on the money path, which needs two approvals.
- Next: Phase 6 (recovery and loss reporting), Phase 7 (retention, erasure,
  verifiable export), Phase 5 (the console Audit section).

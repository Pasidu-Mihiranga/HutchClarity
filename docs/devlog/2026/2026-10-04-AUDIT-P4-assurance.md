# 2026-10-04 - Audit assurance Phase 4 - Detection, alerts, liveness and the playbook

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code |
| Work package | `docs/audit-assurance-plan.md` Phase 4, ADR-0037 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | new `modules/assurance`, platform.audit, platform.persistence, app, interfaces.http, config/policy |

## What changed

- **`clarity.modules.assurance`**, a leaf L4 module: `rules.py` (eight counted
  rules), `alerts.py` (the lifecycle and its closure rules), `service.py`
  (detection, alerts, liveness, playbook), `public.py`, `MODULE.md`.
- Four `/v1/assurance` routes; detection and liveness on a schedule in each API
  process.
- Audit records for domain events carry amounts, outcomes and identifiers.
- 15 policy keys; collections `assurance.alerts` and `assurance.heartbeats`.

## Why

The maintainer's "if some transaction is suspicious from this log, show an
alert with risk". Phases 1 to 3 made the trail trustworthy and readable;
nothing looked at it.

## Decisions made

- **It reads the trail, not the bus.** The plan said "consuming outbox
  events". The trail already holds every domain event (W1) *and* the identity
  and request records the bus never carried. The structuring rule needs both:
  a domain event names the mode (`staff_approved`), never the person, so the
  amount is joined to a human through the `request.performed` record. Reading
  one source also means a rule sees exactly what an investigator sees.
- **Money facts added to the audit detail.** A counted rule had nothing to
  count: the detail held only event metadata. Amounts, outcomes and ids are not
  PII and are what an investigator needs anyway.
- **The second-person rule applies to closing only.** First written across
  every lifecycle move, which meant whoever acknowledged an alert could not
  then investigate it. The test caught it. Acting on an alert needs the
  permission and not being its subject; only the closing move needs the other
  pair of eyes.
- **Liveness is checked from outside the detection loop**, before each cycle: a
  loop that has stopped cannot report that it stopped.
- **One broken rule does not stop the others**: a rule that raises becomes a
  medium finding of its own, and the rest still run.
- **The playbook only moves switches towards safe**, and never back, so it can
  never undo a person's deliberate decision to resume.

## Found while building

**`SwitchBoard` stamps a flip with the real clock, not an injected one.** Under
a frozen clock (the `demo` profile) a switch record's time and a trail record's
time disagree, which `switch_then_pay` compares. It affects the demo profile
only; `full` and `prod` use the real clock for both. Left alone here because
`SwitchBoard` is used well beyond this module, and recorded in ADR-0037 as a
follow-up. The test passes explicit times and says why.

## Docs updated

- [x] `MODULE.md` for the new module; `docs/modules.md`, `ARCHITECTURE.md`,
      plan 21 §11.2 and `test_module_dependencies.py` (leaf declaration)
- [x] ADR-0037 and the index; CHANGELOG; plan revision 7
- [x] OpenAPI snapshot regenerated on purpose (four routes), SDK types
      regenerated; route contract classifies all four as signed-in
- [x] `platform/persistence/schemas.py`: the `assurance` schema owner

## Tests

- `make check`: lint and format clean, `mypy --strict` clean (224 files),
  contracts 3 kept 0 broken; **`1 failed, 2200 passed, 604 skipped`**. The
  failure is the container-proxy test, unchanged.
- `tests/unit/test_assurance.py`: 24 tests, opening with the plan's four
  acceptance tests named as such: five refunds under the cap raising a high
  alert that cites them; a chain break switching `auto_fix_global` off with a
  critical alert; detection going silent; and an alert's subject refused.
  Then the lifecycle, deduplication, escalation once, the threshold boundaries
  (four refunds is not five, small refunds are not structuring, two hours apart
  is not one window), and a broken rule not stopping the others.

## Open issues / next step

- Phase 5: the console Audit section (chain health, trail explorer, alerts,
  monitors, access, recovery) with browser tests.
- Six scenarios from plan 5.7 not yet implemented, each needing a signal the
  trail does not carry or a baseline of normal behaviour: snooping, collusion,
  budget pressure, grant abuse, off-pattern, agent pressure.
- A liveness heartbeat for the audit writer itself (outbox lag).
- `SwitchBoard` and the injected clock (above).

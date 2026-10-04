# 0037 - Assurance is a leaf module that reacts to the trail

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Thanoj Buddhima |
| Plan references | `docs/audit-assurance-plan.md` (Phase 4, sections 5.7 and 5.11), ADR-0029, ADR-0033 to ADR-0036, I1, I10, I22 |

## Context

Phases 1 to 3 made the trail trustworthy, complete and readable by the right
people. Nothing yet *looks* at it. The maintainer asked for suspicious activity
to raise an alert with a risk rating, and the plan adds the two things that
make such a feature honest rather than decorative: alerts that cite their
evidence, and a system that notices when detection itself has stopped.

Three forces shape where this lives:

- **A risk rule must never block a refund.** Detection that sits on the money
  path turns a slow rule into a customer outage.
- **Rules decide nothing** (I1). A finding is a reason for a person to look.
- **"Suspicious" must be counted, not modelled.** `deskops/watch.py` already
  says why: a modelled number is a guess wearing a number's clothes, and the
  desk would act on it.

## Decision

1. **A new L4 module, `clarity.modules.assurance`, with no module edges.** It
   calls no module and no module calls it. It reads the audit trail, the policy
   store and the kill switches, all L2. Declared as a leaf in the dependency
   map and in plan 21 §11.2.
2. **Rules are counts and joins over `AuditRecord`**, with thresholds resolved
   from the policy store `as_of` the moment they apply (I10). Eight rules ship:
   structuring, self-approval, money without proof, switch-then-pay,
   break-glass used, mass audit read, denial spike, brute force. A rule reads
   only record fields, never a payload.
3. **Every alert cites the `seq` numbers that justify it**, so a reviewer reads
   evidence rather than trusting a band.
4. **The structuring rule joins two kinds of record.** A domain event names the
   mode (`staff_approved`), never the person, and the `request.performed`
   record from W2 names the person; joining them on the case is the only way to
   attribute an amount to a human, and it is how an investigator would do it.
5. **Alert lifecycle**: `open`, `acknowledged`, `investigating`, `disposed`,
   with a disposition that always carries a reason. Repeat findings fold into
   the open alert they repeat, so a noisy rule cannot bury a quiet one.
   Unacknowledged alerts escalate once on `assurance.alert.ack_sla`.
6. **Closure rules.** Acting on an alert needs `alert:dispose` and never its
   own subject (ADR-0036 rule 2). *Closing* a high or critical alert needs
   someone other than whoever acknowledged it. The second-person rule applies
   to the closing move only: whoever acknowledges should go on to investigate.
7. **Silence is not safety.** Detection writes a heartbeat on every run,
   including a quiet one, and a liveness check outside the loop turns a missing
   heartbeat into a critical alert. The check runs before each cycle, because a
   loop that has stopped cannot report that it stopped.
8. **The chain-break playbook** moves `auto_fix_global` and `customer_actions`
   to the safe side when verification fails, only ever towards safe, never
   back, and the flip is recorded. A person with the authority turns them on
   again once the break is understood.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Put detection in `deskops` | It would give a desk module a dependency on the trail and the switches, and put risk evaluation next to code that acts on cases. |
| Score risk with a model | I1 and I16. A number nobody can reproduce is not evidence, and the desk would act on it. |
| Call assurance from the money path | A slow or failing rule would become a customer outage. It reacts (I22). |
| Raise one alert per firing | A noisy rule would bury everything else. Repeats fold into the open alert. |
| Let the detection loop check its own liveness | A stopped loop cannot report that it stopped. |

## Consequences

- Four new signed-in routes under `/v1/assurance`; OpenAPI snapshot
  regenerated on purpose.
- Collections `assurance.alerts` and `assurance.heartbeats`, with their own
  schema and role in `full`.
- The audit detail now carries amounts, outcomes and identifiers for money
  events, because a counted rule has nothing to count without them. No PII:
  money and identifiers only (I13).
- Detection runs in each API process on `assurance.detection.interval`.
  Extracting it to `clarity-worker` needs no interface change.
- **`SwitchBoard` stamps a flip with the real clock**, not an injected one, so
  under a frozen clock (the `demo` profile) a switch record's time and a trail
  record's time can disagree, which `switch_then_pay` compares. It affects the
  demo profile only; `full` and `prod` use the real clock for both. Recorded as
  a follow-up rather than changed here, because `SwitchBoard` is used well
  beyond this module.

## Compliance

`tests/unit/test_assurance.py` begins with the plan's four acceptance tests,
named as such, and covers the lifecycle, deduplication, escalation, the
threshold boundaries and a broken rule not stopping the others.
`tests/architecture/test_module_dependencies.py` holds the leaf declaration.

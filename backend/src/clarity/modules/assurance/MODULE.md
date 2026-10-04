# assurance - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.assurance`) |
| Deployable | `clarity-api` today (modular monolith); a `clarity-worker` schedule later |
| Owner | TBD |
| Status | built (`lite` and `full`): audit assurance plan Phase 4, ADR-0037, 2026-10-04 |
| Files | `rules.py`, `alerts.py`, `service.py`, `public.py` |

## 1. Purpose

Watch the audit trail and raise alerts a person owes an answer on: suspicious
patterns counted from the trail, the trail's own integrity, and the silence
that means detection has stopped. It also holds the chain-break playbook, which
moves the kill switches to the safe side when the trail cannot be trusted.

Nothing here decides anything about a case or moves money (I1).

## 2. Public surface (`public.py`)

`AssuranceService`, `Alert`, `AlertState`, `Disposition`, `AlertRefused`,
`AlertNotFound`, `Band`, `Finding`, `RULES`, `SECOND_PERSON_BANDS`,
`PLAYBOOK_SWITCHES`, `CHAIN_BREAK`, `CHECKPOINT_GAP`, `DETECTOR_SILENT`, and
the owned collection names `ALERTS`, `HEARTBEATS`.

## 3. Used by
`clarity.app`, `clarity.interfaces.http`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.kernel` | - |
| `clarity.platform.audit` | reads the trail; appends alert lifecycle records |
| `clarity.platform.config` | thresholds from the policy store; kill switches |
| `clarity.platform.persistence` | `assurance.alerts`, `assurance.heartbeats` |
| `clarity.platform.security` | `Principal`, `Permission` for the closure rules |

**No module edges.** It calls no other module and no module calls it: a rule
that is slow or broken can never block a refund (ADR-0029, ADR-0037).

## 5. Data owned
Collections `assurance.alerts` and `assurance.heartbeats`. Lite uses the shared
memory store; full uses the assurance PostgreSQL schema.

## 6. Invariants
- **Counted, never modelled.** Every rule is a count or a join over trail
  records, with thresholds resolved from the policy store `as_of` the moment
  they apply (I1, I10). No model scores risk.
- Every alert cites the `seq` numbers that justify it, so a reviewer reads
  evidence rather than trusting a score.
- A rule reads only `AuditRecord` fields: never a payload, never customer data.
- Nobody disposes of an alert they are the subject of; a high or critical alert
  is closed by someone other than whoever acknowledged it; disposing needs
  `alert:dispose`, which removes money permissions from its holder (ADR-0036).
- The playbook only ever moves switches to the safe side, never back.
- Detection writes a heartbeat on every run, including a quiet one: a run that
  found nothing and a run that never happened must not look the same.

## 7. Migration status (enterprise-plan 21)
Built in the modular monolith. Detection runs on a schedule in each API
process; extracting it to `clarity-worker` is R6/R7 and needs no interface
change, because it already reacts to the trail rather than being called.

## 8. Tests
- `tests/unit/test_assurance.py`
- `tests/security/test_audit_coverage.py` (the trail the rules read)

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-04 | `docs/devlog/2026/2026-10-04-AUDIT-P4-assurance.md` | Detection, alerts, liveness and the chain-break playbook (Phase 4, ADR-0037) |

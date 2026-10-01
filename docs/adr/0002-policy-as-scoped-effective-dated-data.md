# 0002 - Policy is scoped, effective-dated data with guardrails

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | `docs/improvement-plan.md` A3, A4, A5; alternative design chapter 19 |

## Context
Caps and thresholds were constants in a `PolicyThresholds` class. Three
problems followed.

First, a replay used **today's** thresholds, so "which rules applied when this
charge happened" could not be answered - the question a regulator asks.

Second, the only way to raise a cap for one rule was to raise it for all. That
happened: to make the deck's LKR 3,500 zero-contact refund work (S2, S5), the
global auto-fix cap was raised from LKR 1,000 to 5,000, loosening every other
whitelisted rule at the same time.

Third, nothing bounded a change. A wrong number was one edit away.

## Decision
Policy values are artefacts in `config/policy/*.yaml`:

- **scoped**, with precedence `subscriber > campaign > rule > merchant > segment > channel > region > global`;
- **effective-dated**, and resolved `as_of` the disputed event's time;
- **guard-railed**, with ceilings that overrides cannot exceed;
- **recorded**: every decision stores a `config_snapshot_hash` of the values it used.

The global auto-fix cap returns to LKR 1,000. `DUPLICATE_RELOAD` carries a
scoped ceiling of LKR 3,500, under a guardrail of 5,000.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Constants in code | Thresholds change often; a release per change is slow and risky |
| One global value per key | Forces loosening every rule to loosen one |
| Hand-edited config files | No approvals, no history, no impact preview |

## Consequences
A decision can be reproduced exactly, including under the caps of months ago.
Policy changes need the governance in ADR-0003. Code must not hard-code a
threshold.

## Compliance
`tests/unit/test_policy.py` covers precedence, effective dating, guardrail
rejection, overlap rejection and snapshot stability. A decision without a
`config_snapshot_hash` is a defect.

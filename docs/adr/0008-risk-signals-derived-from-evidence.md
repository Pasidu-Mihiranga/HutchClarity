# 0008 - Risk signals are derived from evidence, not supplied by callers

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | `docs/enterprise-plan/09-rules-decision-receipts.md` §14.1 |

## Context
The decision policy routes a case to staff on a recent SIM swap, a fraud flag
or repeat-refund velocity. If a caller passes those in, anyone who can call the
API can soften them.

## Decision
`build_risk_signals` derives them from the timeline: SIM-swap recency from the
identity source, repeat refunds from the ledger. Safeguard parameters are
derived the same way - the merchant to block comes from the event the rule
matched - so a block cannot be redirected onto a different merchant.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Accept risk signals as request fields | Makes a security control a client-supplied value |

## Consequences
A risk signal exists only if a source reports it. A missing identity source
means the signal is unknown, and the policy treats unknown conservatively.

## Compliance
`tests/unit/test_journeys.py` covers the SIM-swap routing end to end; the API
exposes no field for any risk signal.

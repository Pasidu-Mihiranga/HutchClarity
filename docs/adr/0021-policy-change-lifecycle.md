# 0021 - One lifecycle for every policy change

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | enterprise-plan/20 |

## Context
Packs, prices, caps, regulations and wording change constantly; changes must not need code deploys and must be explainable later.

## Decision
All changeable policy (K1–K8) is versioned, effective-dated, scoped with guardrails, classified C0–C4/E, approved maker ≠ checker, impact-replayed, signed, scheduled and instantly reversible. Decisions store the config snapshot hash and evaluate `as_of` the event time.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Config files edited by hand | No approvals, history or impact preview |
| Code changes for thresholds | Slow; risky |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `enterprise-plan/CHANGES.md`.

## Compliance
No hard-coded policy values in code (review rule + tests); governance audit events for every activation.

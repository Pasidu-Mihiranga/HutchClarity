# 0001 - Cause rules are YAML rule packs, not Python plugins

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Supersedes | - |
| Plan references | `docs/enterprise-plan/09-rules-decision-receipts.md` §13; `docs/improvement-plan.md` D2 |

> **Amended by ADR-0026** (2026-10-02): rule packs stay YAML; the outcome matrix becomes a ZEN decision table; rule *parameters* are moving to the policy store in migration step R3 and are still inside the packs today.

## Context
Cause detection is temporal evidence logic: "a VAS charge with no OTP recorded
before it". It has to be written and reviewed by CX engineers and approved by
compliance, and the plan's own principle is that **rules are data, not code**
(§13.1), so a rule change needs no deploy.

An alternative design argued for Python detector plugins plus GoRules ZEN
decision tables, on the grounds that a home-made DSL costs too much to build
and is less expressive.

## Decision
Keep versioned YAML rule packs evaluated by a small predicate engine
(`exists`, `absent`, `count`, `compare`, with backtracking over bindings).
Rule **parameters** (confidence weights, lookback windows, penalties) move out
of the pack and into the scoped policy store (ADR-0002), so thresholds change
without touching rule logic.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Python detector plugins | The build-cost argument no longer applies: the engine exists, with 6 rules and 21 golden tests. Logic in code also weakens "rules are data": publishing becomes deploying. |
| GoRules ZEN decision tables for outcomes | Our outcome policy is ordered precedence with early returns, which reads more clearly as code than as a table. Revisit if business users need a visual editor. |

## Consequences
A rule change is a data change with golden tests, not a release. The predicate
language is deliberately small and must stay reviewable; anything needing real
computation belongs in a parameter, not a new predicate.

## Compliance
Every rule version carries positive, negative, boundary and property tests.
`rules/packs/*.yaml` is loaded and validated at startup; a malformed pack fails
the load rather than silently shrinking the rule set.

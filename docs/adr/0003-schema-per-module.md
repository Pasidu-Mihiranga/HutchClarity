# 0003 - One Postgres schema and DB role per module; no cross-schema joins

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | docs/enterprise-plan/17 §2.2; 10 §16.1 |

## Context
Shared tables couple modules and block later extraction. Customer data needs defence in depth.

## Decision
Each module owns one schema and one DB role with grants only on its schema. Cross-module data comes from facade calls or event-built projections. Customer-scoped tables use row-level security keyed by `subscriber_ref`.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Shared schema | Coupling; unclear ownership |
| Database per module now | Operational cost; transactions harder at prototype stage |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
Migrations per module; a CI test fails if any SQL references another schema; RLS tests prove cross-subscriber reads are denied.

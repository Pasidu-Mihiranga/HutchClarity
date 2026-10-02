# 0002 - One Postgres schema per module

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
Shared tables couple modules and block extraction. Customer data needs defence in depth.

## Decision
Each module owns one schema and one DB role with grants only on its schema. Cross-module data comes from facade calls or event-built projections. Customer-scoped tables use RLS on `subscriber_ref`.

## Consequences
Migrations are per module. CI fails on cross-schema SQL. SQLite is refused — lite and full both use Postgres.

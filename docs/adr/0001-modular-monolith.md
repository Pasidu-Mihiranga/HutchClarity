# 0001 - Modular monolith with satellite processes

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
A small team cannot afford day-one microservices. Boundaries must still be extractable when trust, keys or scaling diverge.

## Decision
Ship `clarity-api` as a modular monolith: each module owns schema, `public.py` facade, routes and events. Deploy separately only where needed (`clarity-worker`, `clarity-mcp`, `clarity-signer`, gateways, frontends).

## Consequences
Modules communicate through facades and events, never cross-schema SQL. Extraction later is a binding change, not a rewrite.

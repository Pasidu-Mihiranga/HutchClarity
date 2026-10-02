# 0005 - Policy port (Python lite / OPA full)

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
Authorization must deny by default and stay swappable between a fast local driver and a real policy engine.

## Decision
Introduce a `Policy` port. Lite binds `PythonPolicy` (in-process, role→permission map). Full binds `OpaPolicy` with Rego, falling back to Python on OPA outage. Unknown permissions and principals without roles are denied.

## Consequences
Call sites use `policy.require(principal, permission)` only. No ad-hoc role checks in modules. Parity suite covers both drivers.

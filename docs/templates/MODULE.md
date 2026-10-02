# <unit name> - MODULE.md

> Copy this file next to the code when you create a module, service or app. Keep every section true to the code; update it in the same PR whenever the unit's code changes. Write "None" rather than deleting a section.

| Field | Value |
|---|---|
| Kind | module / service / app |
| Layer | L0–L7 (see ARCHITECTURE.md §2) |
| Deployable(s) | clarity-api / clarity-worker / clarity-stream / own service / own app |
| Work package | e.g. R3 (docs/enterprise-plan/21 §7) |
| Owner | @github-handle |
| Status | planned / in-progress / built / integrated / verified |
| Postgres schema | `<schema>` (DB role `<role>`) |

## 1. Purpose
One paragraph: what this unit is responsible for, and what it is explicitly *not* responsible for.

## 2. Public interface (`public.py` facade)
| Method | Input | Output | Errors | Notes |
|---|---|---|---|---|

## 3. HTTP endpoints
| Method & path | Permission | Idempotent? | Contract (OpenAPI operationId) |
|---|---|---|---|

## 4. Events
| Direction | Event type@version | Key | Contract (AsyncAPI) | Handler / producer |
|---|---|---|---|---|
| publishes | | | | |
| consumes | | | | |

## 5. Data owned
| Table | Purpose | Retention | PII? |
|---|---|---|---|

## 6. Permissions declared
| Permission | Meaning | Roles (default) |
|---|---|---|

## 7. Config keys declared (policy artefacts)
| Key | Type | Default | Change class | Owner |
|---|---|---|---|---|

## 8. Dependencies
| Depends on | How (facade call / event / port) | Real or fake today |
|---|---|---|

## 9. Invariants this unit guarantees
- e.g. never executes an action without a valid confirmation token or approval.

## 10. Failure modes and degradation
| Failure | Behaviour | Alert |
|---|---|---|

## 11. Tests
| Type | Location | What it proves |
|---|---|---|

## 12. Operations
Runbook notes, dashboards, feature flags, kill switches.

## 13. Change history
| Date | Devlog entry | Summary |
|---|---|---|

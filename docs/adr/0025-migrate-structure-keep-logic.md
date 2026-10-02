# 0025 - Migrate the prototype: rewrite structure, replace infrastructure, keep proven logic

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Deciders | Architecture (merged plan v1.3); team to ratify |
| Plan references | enterprise-plan/21 |

## Context
The prototype works end to end (438 tests) but is one in-memory process: it cannot run two replicas safely, persists nothing, simulates identity and MCP, and has one orchestration class. The target architecture (chapters 18-20) is built for HUTCH production. A from-scratch rebuild would discard proven logic; leaving the structure as is would block production.

## Decision
Migrate in place with a strangler approach (chapter 21): freeze behaviour as black-box acceptance tests (R0), fix verified defects (R0.5), restructure into the modular monolith layout (R1), add real infrastructure drivers behind parity suites (R2), move core modules to the database and events one at a time (R3), then satellites, frontend, new capabilities and hardening (R4-R7). Domain logic and tests are ported, not rewritten.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Rebuild from scratch to Plan v1 | Throws away tested money-path, policy and receipt logic; longer and riskier |
| Keep the prototype shape | Cannot scale horizontally, persist, federate identity or expose MCP; not adoptable by HUTCH |

## Consequences
The migration plan (chapter 21) and `ARCHITECTURE.md` follow this decision. Changing it needs a superseding ADR and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
R0 acceptance suite stays green at every step; a module's old path is deleted only when the new one passes it; `ARCHITECTURE.md` records each module's migration status.

# 0002 - Modular monolith with separately deployed services

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | enterprise-plan/17 §2, §4; 04 T11 |

## Context
The v1.0 plan listed ~13 microservices from day one. For a small team this creates distributed-monolith overhead before any value, while HUTCH still needs a path to independent services.

## Decision
Build `clarity-api` as a modular monolith (modules with their own schema, `public.py` facade, routes and events). Run as separate processes only where trust, keys or scaling differ: `clarity-worker`, `clarity-stream`, `clarity-mcp`, `clarity-signer`, `clarity-ai-gateway`, `clarity-channel-gateway`, `hutch-sim`, and the three frontends.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Microservices from day one | Network, versioning and deployment cost without benefit at prototype scale |
| Plain monolith | Boundaries erode; extraction later becomes a rewrite |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `enterprise-plan/CHANGES.md`.

## Compliance
A module is extracted by binding its facade to an HTTP client; callers don't change. `import-linter` enforces boundaries in CI.

# 0011 - Record architecture decisions

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | enterprise-plan/CHANGES.md |

## Context
Many developers and AI agents will build modules in parallel. Decisions made in chat or in someone's head get lost and cause inconsistent builds.

## Decision
Every decision about architecture, technology, security, module boundaries or cross-cutting conventions is recorded as an ADR in `docs/adr/` using `docs/templates/ADR.md`. ADRs are never deleted; they are superseded.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Wiki pages | Drift from code; not reviewed in PRs |
| Plan chapters only | Plan is the intent baseline; decisions during build need a lighter, append-only record |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `enterprise-plan/CHANGES.md`.

## Compliance
Reviewers reject PRs that make an unrecorded decision. The ADR index (`docs/adr/README.md`) must list every ADR (checked in review).

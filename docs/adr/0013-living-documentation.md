# 0013 - Living documentation system

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | AGENTS.md; CONTRIBUTING.md |

## Context
Parallel developers and AI agents produce inconsistent code and stale docs unless documentation is part of every change.

## Decision
AGENTS.md defines invariants and a documentation sync matrix. Every unit has a MODULE.md; ARCHITECTURE.md is the living as-built view; walkthroughs record verified flows; every PR adds a devlog file; plan changes go through docs/enterprise-plan/CHANGES.md. Reviewers enforce the sync matrix on every PR.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Docs written at the end | Always stale; judges and HUTCH can't trust them |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
The PR template checklist covers the sync matrix; the `docs-not-needed` label requires a reason.

# 0008 - MCP server: stateless OAuth 2.1 resource server that can only read and propose

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | docs/enterprise-plan/07; 17 §10 |

## Context
HUTCH's AI agents should integrate via MCP; an LLM must never execute money movement or bypass authorization.

## Decision
`clarity-mcp` implements the 2026-07-28 MCP specification (stateless core), validates tokens as an OAuth 2.1 resource server, uses RFC 8693 token exchange downstream (no passthrough), has no database access, and exposes only L1 reads, L2 templated actions and L3 proposals. MCP Apps UI cards are served from `packages/widget`.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| LLM calls REST directly | Prompt injection becomes money movement; no principal binding |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
MCP abuse tests (injection, cross-subscriber, disallowed tools) must pass; zero execute paths exist in the MCP codebase.

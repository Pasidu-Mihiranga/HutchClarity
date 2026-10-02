# 2026-10-02 - PLAN - Backlog by wave and the agentic assistant design

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code (Anthropic), working with the team lead |
| Work package | Planning after R0 |
| PR / commit | branch `docs/backlog-agentic-design` |
| Units touched | docs only |

## What changed
- Plan chapter 22: agentic assistant with flows as versioned state machines, a bounded agent step (tool allowlists, limits, fallback), RAG with mandatory citations, guardrails, per-language evaluation; ADR-0030
- `docs/backlog`: 43 issues in six waves (W0 baseline wiring, W1 core modules, W2 AI foundation, W3 knowledge, RAG and assistant, W4 channels and intelligence, W5 frontend and hardening), each with context, scope, dependencies, Given/When/Then acceptance tests with target test files, and a Definition of Done; index with a wave graph, labels and a GitHub import script
- Plan v1.5 (README, CHANGES.md); AGENTS.md, README.md and ARCHITECTURE.md link the backlog

## Why
The team builds bottom-up: wire the baseline (events, repositories, bus, outbox, PostgreSQL) first, then modules on top, then the assistant on the AI foundation.

## Tests
- Docs only. Issue tables validated, every dependency resolves to an issue, no em dashes, links checked.

## Next step
- Import the issues into GitHub; start W0 with B01, B02 and B07 in parallel

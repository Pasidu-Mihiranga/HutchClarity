# 0030 - Bounded agency: flows as state machines, tools by allowlist, grounded RAG

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Deciders | Architecture (plan v1.5); team to ratify |
| Plan references | enterprise-plan/22; 07 §10-11; 08 §12 |

## Context
The chatbot must handle open, multilingual questions (an "agentic" assistant), yet the system's core promise is that rules decide and the LLM explains. A free-running agent that chooses its own steps and tools would be hard to test, audit or replay, and a single prompt injection could steer it. Knowledge answers must be traceable to approved, effective sources.

## Decision
- Conversations run as **versioned flows (state machines)** published as policy content. A model may act only inside states marked agentic, choosing among that state's **tool allowlist** and filling arguments against a JSON schema; invalid plans fall back to the deterministic step.
- **Limits per turn and session** (tool calls, tokens, time); tool results are untrusted data.
- Tools are **MCP tools bound to the session subject**: read and propose only; confirmation stays outside the model.
- Knowledge answers are **retrieval-augmented with mandatory citations** from owner-approved, effective-dated sources; no source means "I don't know" and a person.
- Every step works **without a model** (keyword intake, templates, BM25); models improve it when configured.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Free-running agent (model picks any tool, any step) | Untestable and unauditable; injection can redirect it; conflicts with I1 |
| Rules-only chatbot | Brittle for Singlish and free-form questions; poor experience |
| Fine-tuned model without retrieval | Knowledge goes stale with every pack or regulation change; no citations |

## Consequences
Flows, intents and prompts become reviewed artefacts under plan 20; the knowledge module owns ingestion and retrieval; MCP gains `search_knowledge` and `get_network_status`; evaluation sets per language gate releases.

## Compliance
Flow and planner tests reject disallowed tools and amount fields; the safety eval set must show zero executed actions; citation verifier tests; per-language gates in nightly evaluation.

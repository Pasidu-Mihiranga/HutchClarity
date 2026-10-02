# 0009 - No language model is configured by default

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | `docs/enterprise-plan/08-ai-architecture.md` §12.2; `docs/submission/AI_DISCLOSURE.md` |

## Context
Deck S7 states that Clarity "works without the LLM (templates)". A prototype
that only works with a model has not demonstrated that claim, and a live demo
that depends on a free-tier quota can fail in the room.

## Decision
The AI gateway ships with a template provider and no model. Explanations are
CX-approved templates in Sinhala, Tamil and English. Masking, the deterministic
verifier, routing and fallback are all built and tested around it. Setting
`CLARITY_MODEL_BASE_URL` routes through any OpenAI-compatible endpoint
(self-hosted vLLM, Ollama, or a hosted provider) with no change to the
guardrails.

Free-tier providers may use prompts to improve their products, so **only
synthetic, masked data** may be sent to one.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Ship with a hosted model | Needs a key to demo, can fail on quota, and risks real data on a free tier |
| Call it a stub | It is not a stub. It is the deck's stated fallback path, running. |

## Consequences
Measured token use is zero, and the AI disclosure says so and explains why.
Sinhala and Tamil template wording has **not** been reviewed by native
speakers; that gate is recorded in the known limitations.

## Compliance
`scripts/measure_tokens.py` reports measured usage per journey.
`tests/unit/test_ai.py` covers the verifier blocking invented amounts and
unauthorised promises, and fallback on provider outage.

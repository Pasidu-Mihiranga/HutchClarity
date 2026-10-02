# 0009 - AI gateway with model roles; Gemini + Groq free tiers for the prototype

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | docs/enterprise-plan/18 §4; 08 |

## Context
No GPUs or budget for the prototype; HUTCH will later choose its own provider. Cheap models must handle most text; reasoning only when needed.

## Decision
Code requests logical roles (`fast-text`, `extract`, `reason`, `judge`, `guard`, `embed`, `stt`, `tts`); `config/ai/models.yaml` maps them to providers with fallback chains. Prototype: Gemini Flash-Lite for fast text/extraction, Groq gpt-oss-120b for reasoning (Gemini Flash fallback), self-hosted BGE-M3 embeddings. Only synthetic, PII-masked data is sent; Groq ZDR enabled. Quota-aware buckets, priority queue, record/replay in CI.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Single provider | Free-tier quotas too small; no fallback |
| Self-hosted only | No GPUs in the prototype |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
No model ID outside config (grep check); masking enforced in the gateway; usage ledger produces measured token figures.

# 0007 - Gemini + Groq via model roles

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
No GPU budget for the prototype. Free-tier quotas are small; a single provider fails under load.

## Decision
Code requests logical roles (`fast-text`, `extract`, `reason`, `judge`, `guard`, `embed`, `stt`, `tts`). `config/ai/models.yaml` maps them: Groq for fast-text/extract/stt/tts; Gemini for reason/judge/guard; local BGE for embed — each with fallback chains. PII is masked before send; cassettes enable record/replay in CI.

## Consequences
No model ID outside config. Template preference stays on by default (`AI_PREFER_TEMPLATES=true`). Usage is ledgered for measured token figures.

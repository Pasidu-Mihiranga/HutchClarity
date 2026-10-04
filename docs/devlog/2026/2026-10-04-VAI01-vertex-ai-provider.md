# 2026-10-04 - VAI01 - Vertex AI provider

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | VAI01 (plan 19 §3; 22 §4) |
| PR / commit | #60 / pending |
| Units touched | ai, app composition, deploy |

## What changed

- Added a Vertex `generateContent` provider authenticated by short-lived ADC tokens.
- Routed masked text roles to Vertex while preserving local deterministic fallbacks.
- Added a read-only external credential mount for the synthetic VPS deployment.
- Corrected the CI Compose fixture so its root-created dummy env file is readable.

## Why

VAI01 #61 requests use of the supplied Vertex AI service account without
weakening Clarity's rule authority, masking boundary or offline default.

## Decisions made

- `google-auth[requests]` is used only for ADC token acquisition. It is
  Apache-2.0 and satisfies I17.
- The service-account key remains outside Git. Workload identity is the
  production target; the key file is acceptable only for this synthetic demo VPS.

## Docs updated

- [x] Backlog and changelog
- [x] Architecture model status
- [x] Deployment and environment configuration
- [ ] No module `MODULE.md` applies because `clarity.ai` is a platform layer, not a domain module

## Tests

- Focused provider and settings tests: 10 passed.
- Synthetic live Vertex probe: passed; token usage returned.
- Full gate and VPS re-verification pending.

## Open issues / next step

Run `make check`, deploy the immutable candidate, and verify fallback plus live
masked generation before closing #61.

# [VAI01] Vertex AI provider with safe fallback

| Field | Value |
|---|---|
| Wave | W2 AI foundation |
| Area | `ai` |
| Priority | P1 |
| Depends on | A01, A02, A03 |
| Plan | 19 §3; 22 §4 |
| Labels | `area:ai`, `priority:p1`, `type:feature` |

## Scope

- Authenticate Vertex AI through Application Default Credentials kept outside the repository.
- Route text roles to Vertex without changing the rule, action or verification boundaries.
- Preserve masking, recorded-response isolation and deterministic local fallbacks.
- Mount the credential read-only in the synthetic single-VPS deployment.

## Acceptance tests

- Provider contract tests prove the masked request shape and usage accounting without a live call.
- A synthetic live probe succeeds with the supplied service account.
- No credentials or real customer data enter Git, logs or model prompts.
- `make check` and the VPS health checks pass.

GitHub: #61.

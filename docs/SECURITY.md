# Security Policy

## Reporting a vulnerability

Do not open a public issue. Contact the team security owner privately (see
CODEOWNERS once assigned) with steps to reproduce. We acknowledge within
2 working days.

## Rules for contributors

- **No secrets in the repository.** Use a git-ignored `.env`; `.env.example`
  holds dummy values only. CI runs a gitleaks placeholder (wire the real
  scanner when ready).
- **No real personal or HUTCH data** anywhere in the repo, tests, fixtures,
  screenshots or LLM prompts. Use synthetic data from mocks / `hutch-sim`.
- Free-tier AI providers receive only synthetic, PII-masked data.
- Money-path and security-sensitive paths require careful review
  (`modules/actions`, `modules/decision`, `modules/receipts`, `rules/`,
  `services/signer`).
- New runtime dependencies must have an OSI-friendly licence where possible.

## AuthZ and MCP

- Deny by default: OPA policy in `deploy/opa/authz.rego` (Python policy driver
  in lite).
- MCP tools require a Bearer token; `propose_action` always needs an
  `idempotency_key`. There is no execute path over MCP.

## Design references

- Enterprise plan security chapter: `docs/enterprise-plan/11-security-privacy-audit.md`
- ADRs under `docs/adr/`

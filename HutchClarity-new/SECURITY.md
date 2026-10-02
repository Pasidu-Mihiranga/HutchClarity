# Security Policy

## Reporting a vulnerability
Do not open a public issue. Contact the team security owner privately (see CODEOWNERS once assigned) with steps to reproduce. We acknowledge within 2 working days.

## Rules for contributors
- **No secrets in the repository.** Use a git-ignored `.env`; `.env.example` holds dummy values only. CI runs secret scanning.
- **No real personal or HUTCH data** anywhere in the repo, tests, fixtures, screenshots or LLM prompts. Use synthetic data from `hutch-sim`.
- **Free-tier AI providers receive only synthetic, PII-masked data** (Gemini's unpaid tier may use prompts to improve Google products). Groq Zero Data Retention must be enabled on the team account.
- Money-path and security-sensitive paths require two reviewers (CODEOWNERS + branch protection).
- New runtime dependencies must have an OSI licence and pass the dependency scan.

## Security design
See [enterprise-plan/11-security-privacy-audit.md](enterprise-plan/11-security-privacy-audit.md) and [enterprise-plan/17-build-blueprint.md §5](enterprise-plan/17-build-blueprint.md).

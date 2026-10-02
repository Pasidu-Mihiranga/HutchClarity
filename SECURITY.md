# Security Policy

## Reporting a vulnerability
Do not open a public issue. Contact the team security owner privately (see CODEOWNERS once assigned) with steps to reproduce. We acknowledge within 2 working days.

## Rules for contributors
- **No secrets in the repository.** `.env` is git-ignored; `.env.example` holds dummy values only.
- **No real personal or HUTCH data** anywhere: code, tests, fixtures, screenshots or LLM prompts. Use the synthetic world.
- **Free-tier AI providers receive only synthetic, PII-masked data** (Gemini's unpaid tier may use prompts to improve Google products). Groq Zero Data Retention must be enabled on the team account.
- Development identity routes (OTP inbox, staff role picker) exist only in the synthetic profiles (`demo`, `full`) and return 404 in `prod`.
- Money-path and security-sensitive paths need two reviewers.
- New runtime dependencies need an OSI licence (plan 19 §1).

## Security design
[docs/enterprise-plan/11-security-privacy-audit.md](docs/enterprise-plan/11-security-privacy-audit.md) (threats TH1-TH19) and [docs/enterprise-plan/18-build-blueprint.md §5](docs/enterprise-plan/18-build-blueprint.md) (identity and permissions).

# 2026-10-04 - staff login and Vertex on the desk

| Field | Value |
|---|---|
| Author(s) | agent: Grok |
| Work package | VAI01, console sign-in |
| PR / commit | not committed |
| Units touched | iam, ai, app, http, console, deploy |

## What changed

- `POST /v1/auth/staff/login` checks a staff directory and the server assigns the role. A configured directory makes `POST /v1/auth/staff/session` return 404. Both stay 404 in `prod`.
- The console header is a username, password, and optional step-up code. The role chips and the Desk seed buttons are gone.
- Vertex AI is bound for text roles when `CLARITY_VERTEX_PROJECT` is set. `AI_PREFER_TEMPLATES=false` is required or templates still answer. Speech stays on Groq, then a local refusal.
- The audit checkpoint path is narrowed so `KEYS_DIR` unset does not fail mypy. That was the failure that skipped CD (run 37188183686).
- `google-auth[requests]` is Apache-2.0, used only for ADC.

## Why

The role picker let any caller choose finance. The deployed image had no Vertex provider, and CI never shipped the audit commit because mypy rejected `container.py`.

## Decisions made

- Directory unset keeps the old session route, so the existing suite still mints tokens. `make dev` and `make dev-e2e` set the synthetic file, which closes the route there.
- Live Vertex is not wrapped in a cassette. A missing cassette would 500 an explanation. Replay remains the path when templates are preferred or a test injects a provider.
- The VPS image is built on the box from this tree. It is not a GitHub release. The next CD from `main` will replace it.

## Docs updated

- [x] MODULE.md of: iam
- [ ] ARCHITECTURE.md / modules.md
- [x] Walkthrough: WT-13
- [x] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests

- `pytest` staff directory, Vertex provider (fake HTTP), IAM, AI roles, model-id architecture, settings env example, route contract, migration defects, audit coverage: passed after the Vertex response fixture was given a request.
- OpenAPI snapshot and SDK regenerated.
- `mypy` on container, providers, directory, and the HTTP app: clean.
- VPS healthcheck: recorded after the root deploy.

## Takeover (agent: Claude Code, Claude Opus 5.5)
- Taken over from the uncommitted tree and committed as is (`a0e5bfb`), then hardened.
- Staff directory stores salted scrypt hashes (`password_hash`, `step_up_hash`), never secrets; a plaintext field is refused at load; an unknown username costs one scrypt like a wrong password. `scripts/staff_password.py` makes hashes from stdin. The synthetic file was converted with the same dev passwords, which stay in `frontend/e2e/session.ts`.
- Nginx: `/v1/auth/` has its own limit, 10 per minute per IP with a burst of 20, answering 429.
- VPS: service account at `/opt/hutch-clarity/private/google-service-account.json` and a staff directory with generated passwords, both uid 10001 and mode 0400; `.env.production` (backed up first) gained the Vertex settings, `AI_PREFER_TEMPLATES=false` and `CLARITY_STAFF_DIRECTORY_FILE`. The plaintext staff passwords live only on the operator's machine.
- Live Vertex check with the service account and synthetic facts: `gemini-2.5-flash` answered (89 input, 22 output tokens).
- `GEMINI_API_KEY` and `GROQ_API_KEY` are not read by the backend. With Vertex configured, the Gemini and Groq fallbacks in `models.yaml` are not registered, so the chain falls back to templates.

## Open issues / next step

The service-account key was pasted in chat earlier. Rotate it. This tree is not committed, so GitHub CD will not keep this image.

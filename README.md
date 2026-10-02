# Hutch Clarity

**Explain every rupee. Fix it by rule. Prove it won't happen again.**

| | |
|---|---|
| Team | **[Team name - to fill]** · [University and batch - to fill] |
| Track | **Track A - Resolve & Support:** Intelligent Automation & Root-Cause AI |
| Status | Working prototype (546 tests). Migrating into the target architecture: step R1 done ([plan 21](docs/enterprise-plan/21-migration-and-deployment-plan.md)). |

One platform for HUTCH customers and staff: website, Hutch app, WhatsApp, SMS/USSD and the Clarity Desk staff console. For any charge it explains the exact cause with evidence, fixes safe cases by deterministic rule, and issues a signed, QR-verifiable **Trust Receipt** as proof.

> **Hackathon prototype.** All HUTCH systems are **simulated** and all data is **synthetic**. No HUTCH APIs, credentials or production data are used. See [Known limitations](#known-limitations).

## Problem statement
Prepaid customers lose money and nobody can say why: reloads taken twice, surprise VAS debits, "unlimited" data that stops at a fair-use cap, and support that does not resolve. The evidence exists but is split across payment, charging, catalogue, consent and usage systems. See [plan 01](docs/enterprise-plan/01-executive-summary-problem.md).

## Core principle: rules decide, the LLM explains

| Deterministic (decides, moves money) | AI (language only) |
|---|---|
| Timeline from system records, YAML rule packs, decision policy, caps and budgets, tool layer, receipt signing | Multilingual intake, explanation drafting, summaries, retrieval, clustering |

The LLM can never authorize a refund or a service change. Through MCP it may only **propose**; execution needs a confirmation token minted outside the model (customer tap, staff approval, or policy for a whitelisted auto-fix).

## Key features
**Why?** with cause, evidence and ruled-out causes · one-tap fixes · zero-contact refunds · signed, chained Trust Receipts with QR verification · Clarity Desk (queue by money at stake, case cockpit, step-up and four-eyes approval) · policy as scoped, effective-dated data with guardrails, kill switches, replay impact reports and maker-checker · Complaint Autopsy · Foresight · MCP tools that can read and propose only · Sinhala, Tamil and English.

## Architecture
A **modular monolith** with enforced layers, designed to become microservices where it pays off:

`kernel → contracts → integration → platform → ai → modules → app → interfaces → entrypoints`

Each domain module is reachable only through its `public.py`; the money-moving code is reachable only from the case orchestration and the composition root. Target runtime: **containers for the money path, serverless at the edges** (ADR-0028). Details: [ARCHITECTURE.md](ARCHITECTURE.md) (as built) and [plan 18](docs/enterprise-plan/18-build-blueprint.md) / [21](docs/enterprise-plan/21-migration-and-deployment-plan.md) (target).

## Technology stack
Python 3.12+ · FastAPI · Pydantic v2 · YAML rule packs · Ed25519 (`cryptography`) · import-linter · pytest + Hypothesis · ruff · mypy --strict. Target stack (PostgreSQL 18, Kafka, Keycloak, OPA, ZEN, Next.js, MCP SDK, Gemini + Groq by role) and the reasons: [plan 19](docs/enterprise-plan/19-tech-stack-and-ai.md).

## Setup
Needs **only Python 3.12+** (no Docker, database or broker; `lite` profile).

```bash
make setup     # creates .venv and installs the backend with dev tools
make check     # lint, types, import contracts, tests
```

## How to run and test

```bash
make demo      # walk the four journeys in the terminal
make dev       # UI + API on http://localhost:8000
```

| Page | What it is |
|---|---|
| <http://localhost:8000/> | Customer **Why?** journey: sign in with the simulated OTP inbox, see the cause with evidence, confirm in one tap, keep the receipt |
| <http://localhost:8000/desk> | **Clarity Desk**: queue by money at stake, case cockpit, approvals (simulated staff sign-in; never available in `prod`) |
| <http://localhost:8000/v/TR-2027-000001> | **Public receipt check**: what the QR code opens |
| <http://localhost:8000/docs> | API reference (OpenAPI) |

`POST /v1/demo/reset` restores the synthetic data so the demo can run again.

**Next.js apps (optional, Node 18+):** `make web-install`, then `make web-customer` (port 3000), `make web-console` (3001) or `make web-verify` (3002) against the API on port 8000. See [frontend/README.md](frontend/README.md). The full storyboard is [docs/submission/DEMO_SCRIPT.md](docs/submission/DEMO_SCRIPT.md).

## API / external services
- **HUTCH systems:** none required; all are simulated (labelled in every response).
- **LLM:** none required; explanations come from CX-approved templates by default (ADR-0009). An OpenAI-compatible provider can be enabled by environment variables (synthetic data only).

## Known limitations
1. **No real HUTCH integration.** Every HUTCH system is a mock driver; real interfaces are unconfirmed.
2. **Synthetic data only.**
3. Rule thresholds, caps and budgets are illustrative, not validated by HUTCH Finance.
4. **In memory, single process.** Nothing survives a restart, and only one instance may run until migration step R3.
5. **Identity is simulated:** an own token issuer, a simulated SMS inbox, and a staff role picker available only in the synthetic profiles (refused in `prod`).
6. **MCP has no network transport yet** (migration step R4).
7. **No language model is configured**, so measured token use is zero.
8. Sinhala and Tamil wording has **not been reviewed by native speakers**.

Full detail: [docs/submission/KNOWN_LIMITATIONS.md](docs/submission/KNOWN_LIMITATIONS.md).

## For reviewers

| Document | What it covers |
|---|---|
| [docs/submission/AI_DISCLOSURE.md](docs/submission/AI_DISCLOSURE.md) | AI/LLM declaration with measured token numbers |
| [docs/submission/KNOWN_LIMITATIONS.md](docs/submission/KNOWN_LIMITATIONS.md) | Exactly where the prototype stops |
| [docs/submission/DEMO_SCRIPT.md](docs/submission/DEMO_SCRIPT.md) | A 6-minute walkthrough |
| [docs/enterprise-plan/](docs/enterprise-plan/README.md) | The plan from here to production (v1.3) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | What is built, and where it differs from the plan |
| [docs/adr/](docs/adr/README.md) | Why each significant decision was made |

## Third-party components
See [backend/pyproject.toml](backend/pyproject.toml). Key: FastAPI, Uvicorn, Pydantic, PyYAML, cryptography, PyJWT, python-ulid, qrcode, SQLAlchemy; dev: pytest, Hypothesis, ruff, mypy, import-linter; optional: Playwright (receipt PNG/PDF).

## AI tools / models used
No model is configured by default. Model roles and the opt-in provider plan: [plan 19 §4](docs/enterprise-plan/19-tech-stack-and-ai.md). Declaration: [docs/submission/AI_DISCLOSURE.md](docs/submission/AI_DISCLOSURE.md).

## For contributors
[AGENTS.md](AGENTS.md) (rules for people and AI agents) · [CONTRIBUTING.md](CONTRIBUTING.md) · [docs/modules.md](docs/modules.md) · [docs/WALKTHROUGHS.md](docs/WALKTHROUGHS.md) · [docs/devlog/](docs/devlog/README.md)

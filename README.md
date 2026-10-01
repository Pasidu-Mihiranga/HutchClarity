# Hutch Clarity

**Explain every rupee. Fix it by rule. Prove it won't happen again.**

One platform for HUTCH customers and staff — website, Hutch app, WhatsApp, SMS/USSD and the Clarity Desk staff console. For any charge it explains the exact cause with evidence, fixes safe cases by deterministic rule, and issues a signed, QR-verifiable **Trust Receipt** as proof.

> **Hackathon prototype.** All HUTCH systems are **mocked** and all data is **synthetic**. No HUTCH APIs, credentials or production data are used. See [Known limitations](#known-limitations).

## Core principle: rules decide, the LLM explains

| Deterministic (decides, moves money) | AI (language only) |
|---|---|
| Timeline from system records, cause rules, decision policy, caps and budgets, tool layer, receipt signing | Multilingual intake, explanation drafting, summaries, retrieval, clustering |

The LLM can never authorize a refund or a service change. Through MCP it may only **propose**; execution needs a confirmation token minted outside the model (customer tap or staff approval).

## Status

Implementation has started. Progress is tracked in [`agent.md`](agent.md) §6a.

| Milestone | Status |
|---|---|
| P1 Foundation (schemas, canonical hashing) | done |
| P2 Mock HUTCH systems + adapters | done |
| P3 Deterministic core (timeline, rules, decision, tool layer) | done |
| P4 Trust Receipts (Ed25519, chain, verify) | done |
| P5 API (`/v1`, 15 endpoints) | done (persistence in-memory) |
| P7 Web + Clarity Desk | done |
| P6 AI + MCP | todo |
| P8 Autopsy, Foresight, submission pack | todo |

193 tests pass; `ruff` and `mypy --strict` are clean.

## Documentation

The full enterprise plan (52 sections, 39 diagrams) is in [`docs/enterprise-plan/`](docs/enterprise-plan/README.md): architecture, integration strategy, MCP design, security, delivery plan and Gantt.

## Repository layout

The plan's §43 describes the production monorepo. The prototype implements it as one Python package whose modules map 1:1 to those components:

| Plan (§43) | Prototype |
|---|---|
| `packages/schemas`, `packages/events` | `src/clarity/schemas`, `src/clarity/events` |
| `integrations/framework` + adapters + mocks | `src/clarity/integrations` |
| `services/case-service`, `timeline-builder`, `rule-engine`, `decision-policy`, `tool-layer`, `receipts` | `src/clarity/core/{cases,timeline,rules,decision,tools,receipts}` |
| `ai/`, `mcp/server`, `services/bff-api` | `src/clarity/{ai,mcp,api}` |
| `rules/packs` | `rules/packs` (YAML data — rules are data, not code) |

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
make check     # lint, types, import contracts, tests
```

### See it work

```bash
# Walk all four journeys in the terminal
.venv/bin/python scripts/demo.py

# Or run the whole prototype — UI and API in one process
.venv/bin/uvicorn clarity.api.main:app
```

| Page | What it is |
|---|---|
| <http://localhost:8000/> | Customer **Why?** journey — ask, see the cause with evidence, confirm in one tap, keep the receipt |
| <http://localhost:8000/desk> | **Clarity Desk** — queue by money at stake, case cockpit, supervisor approval |
| <http://localhost:8000/v/TR-2027-000001> | **Public receipt check** — what the QR code opens |
| <http://localhost:8000/docs> | API reference (OpenAPI) |

`POST /v1/demo/reset` restores the synthetic data so the demo can be run again.

A full journey over HTTP:

```bash
CASE=$(curl -s -X POST localhost:8000/v1/cases \
  -H 'content-type: application/json' \
  -d '{"msisdn":"0771234567","channel":"app","language":"si"}' | jq -r .case_id)

curl -s -X POST localhost:8000/v1/cases/$CASE/evaluate | jq       # cause + ruled out
PLAN=$(curl -s -X POST localhost:8000/v1/cases/$CASE/proposals \
  -H 'content-type: application/json' -d '{"created_by":"channel:web"}' | jq -r .plan_id)
curl -s -X POST localhost:8000/v1/cases/$CASE/confirm \
  -H 'content-type: application/json' -d "{\"plan_id\":\"$PLAN\"}" | jq
curl -s -X POST localhost:8000/v1/receipts/TR-2027-000001/verify | jq
```

## For reviewers

| Document | What it covers |
|---|---|
| [`docs/submission/AI_DISCLOSURE.md`](docs/submission/AI_DISCLOSURE.md) | AI/LLM declaration with **measured** token numbers (Guidelines §6) |
| [`docs/submission/KNOWN_LIMITATIONS.md`](docs/submission/KNOWN_LIMITATIONS.md) | Exactly where the prototype stops |
| [`docs/submission/DEMO_SCRIPT.md`](docs/submission/DEMO_SCRIPT.md) | A 6-minute walkthrough |
| [`docs/enterprise-plan/`](docs/enterprise-plan/README.md) | The 52-section plan from here to production |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | What is actually built, and where it differs from the plan |
| [`docs/adr/`](docs/adr/README.md) | Why each significant decision was made |

```bash
.venv/bin/python scripts/measure_tokens.py   # measured AI usage per journey
```

## Known limitations

1. **No real HUTCH integration.** Every HUTCH system is a mock driver; real interfaces are unknown and unconfirmed.
2. **Synthetic data only.** Subscribers, charges, payments, consents and complaints are generated.
3. Rule thresholds, caps and budgets are illustrative and not validated by HUTCH Finance.
4. **No authentication** on the API, and all state is **in memory** — nothing survives a restart.
5. **No language model is configured.** Explanations come from CX-approved templates, which is the deck's "works without the LLM" path; measured token use is therefore zero.
6. Sinhala and Tamil wording has **not been reviewed by native speakers**.

Full detail in [`docs/submission/KNOWN_LIMITATIONS.md`](docs/submission/KNOWN_LIMITATIONS.md).

## Third-party components

See [`pyproject.toml`](pyproject.toml). Key: Pydantic, FastAPI, SQLAlchemy, PyYAML, cryptography (Ed25519), pytest, Hypothesis, Ruff, mypy.

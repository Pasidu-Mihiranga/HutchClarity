# Module Registry

One row per unit. Every domain module has a `MODULE.md` next to its code and a `public.py` that is its only import surface (test-enforced). Migration steps refer to [plan 21 §7](enterprise-plan/21-migration-and-deployment-plan.md).

Status values: `planned` → `built` (works in `lite`) → `migrated` (on the target infrastructure in `full`) → `verified`.

## Built today

| Unit | Layer | Path | MODULE.md | Status | Next migration step |
|---|---|---|---|---|---|
| kernel | L0 | `backend/src/clarity/kernel/` | - | built | - |
| contracts | L0 | `backend/src/clarity/contracts/` | - | built; **domain event payloads typed and versioned** (`events.py`, #10) | AsyncAPI generation (R2) |
| integration (ports, mock and HTTP drivers) | L1 | `backend/src/clarity/integration/` | - | migrated (simulated) | HUTCH sandbox mappings require confirmation |
| integration: mock store (simulated HUTCH estate in SQL) | L1 | `backend/src/clarity/integration/drivers/mock/store/` | - | built by the team | Persistent hutch-sim deployment wiring (X03) |
| hutch-sim (SIMULATED HUTCH systems over HTTP) | service | `services/hutch-sim/` | - | built | Deployment image and Compose wiring (X03) |
| resolution | L4 | `backend/src/clarity/modules/resolution/` | case, timeline, detection, decision, actions, receipts | built | Orchestration split out of `case` (M-CASE #34). The only module allowed to import `actions.capability`. |
| platform: config, audit, messaging, persistence, observability, content, security | L2 | `backend/src/clarity/platform/` | - | built | Persistence port with in-memory and PostgreSQL drivers, schema and role per module, row-level security (B02, B05); event bus port with in-process and Kafka drivers (B03); transactional outbox, relay and consumer framework (B04); traces and masked structured logs (B08). OPA with R2. |
| ai (gateway, providers, PII, verifier) | L3 | `backend/src/clarity/ai/` | - | built (no model) | Model roles, cassettes (R4) |
| actions | L4 | `backend/src/clarity/modules/actions/` | [MODULE.md](../backend/src/clarity/modules/actions/MODULE.md) | built | DB idempotency, row locks (R3) |
| case | L4 | `backend/src/clarity/modules/case/` | [MODULE.md](../backend/src/clarity/modules/case/MODULE.md) | built | Split orchestration; event-driven receipts (R3) |
| decision | L4 | `backend/src/clarity/modules/decision/` | [MODULE.md](../backend/src/clarity/modules/decision/MODULE.md) | migrated | ZEN-compatible decision table and parity suite (M-DEC) |
| detection | L4 | `backend/src/clarity/modules/detection/` | [MODULE.md](../backend/src/clarity/modules/detection/MODULE.md) | migrated (10 of 16 rules) | Product validation of remaining candidates |
| governance | L4 | `backend/src/clarity/modules/governance/` | [MODULE.md](../backend/src/clarity/modules/governance/MODULE.md) | migrated | Policy Studio lifecycle and persisted approvals/activations (M-GOV) |
| iam | L4 | `backend/src/clarity/modules/iam/` | [MODULE.md](../backend/src/clarity/modules/iam/MODULE.md) | migrated | Keycloak/OPA full drivers and shared identity state (M-IAM) |
| receipts | L4 | `backend/src/clarity/modules/receipts/` | [MODULE.md](../backend/src/clarity/modules/receipts/MODULE.md) | migrated | OpenBao signer driver and isolated render job (M-RCPT) |
| reconciliation | L4 | `backend/src/clarity/modules/reconciliation/` | [MODULE.md](../backend/src/clarity/modules/reconciliation/MODULE.md) | built | Production worker schedule (M-REC) |
| notifications | L4 | `backend/src/clarity/modules/notifications/` | [MODULE.md](../backend/src/clarity/modules/notifications/MODULE.md) | built | Channel gateway providers and callbacks (N02) |
| timeline | L4 | `backend/src/clarity/modules/timeline/` | [MODULE.md](../backend/src/clarity/modules/timeline/MODULE.md) | migrated | HUTCH sandbox mappings require confirmation |
| conversation | L4 | `backend/src/clarity/modules/conversation/` | [MODULE.md](../backend/src/clarity/modules/conversation/MODULE.md) | built by the team (keyword intake, no LLM) | Intents as policy content; optional `extract` role (R4) |
| autopsy | L4 | `backend/src/clarity/modules/autopsy/` | [MODULE.md](../backend/src/clarity/modules/autopsy/MODULE.md) | built | Serverless batch job (R6/R7) |
| foresight | L4 | `backend/src/clarity/modules/foresight/` | [MODULE.md](../backend/src/clarity/modules/foresight/MODULE.md) | built | Serverless batch job (R6/R7) |
| app (composition root, MCP view) | L5 | `backend/src/clarity/app/` | - | built | Profiles `full`, `prod` (R2) |
| interfaces.http (`/v1`, static UI) | L6 | `backend/src/clarity/interfaces/http/` | - | built | Static UI retires once the Next.js apps are verified (R5) |
| customer-web, console, verify (Next.js 14) | L7 apps | `frontend/apps/*` | `frontend/README.md` | built by the team (R5 started early); build not yet verified on `dev` | Verify build; align to Next.js 16 per plan 19 |
| ui, sdk, i18n, widget | packages | `frontend/packages/*` | `frontend/README.md` | built by the team | `sdk` has 2 methods with no backend route (`detect`, `decide`, marked) |
| interfaces.mcp | L6 | `backend/src/clarity/interfaces/mcp/` | - | built (in-process only) | Real MCP server `clarity-mcp` (R4) |
| entrypoints | L7 | `backend/src/clarity/entrypoints/` | - | built | Worker and stream entry points (R3) |

## Planned

| Unit | Kind | Target path | Migration step |
|---|---|---|---|
| clarity-mcp (MCP SDK, Streamable HTTP, OAuth 2.1) | service | `services/mcp/` | R4 |
| clarity-signer | service | `services/signer/` | R4 |
| clarity-ai-gateway | service | `services/ai-gateway/` | R4 |
| clarity-channel-gateway (WhatsApp, SMS/USSD) | service | `services/channel-gateway/` | R4 |
| proactive (stream detectors) | module | `backend/src/clarity/modules/proactive/` | R6 |
| knowledge / RAG | module | `backend/src/clarity/modules/knowledge/` | R6 |
| insights | module | `backend/src/clarity/modules/insights/` | R6 |
| desk-ops (bulk fix, merchant watch, regulator pack) | module | `backend/src/clarity/modules/deskops/` | R6 |

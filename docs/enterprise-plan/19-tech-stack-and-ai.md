# Hutch Clarity - Enterprise Tech Stack, AI Providers & Plan Alignment

[← 18-build-blueprint.md](18-build-blueprint.md) · [← Plan index](README.md) · [20-policy-change-management.md →](20-policy-change-management.md)

> This chapter fixes the technology choices using **enterprise selection criteria**, not team preference. It also defines the LLM strategy for the prototype (Gemini + Groq free tiers) and how HUTCH swaps in its own models later. Finally, it lists which earlier chapters need updating.
> Versions are **target majors**. Exact patch versions are pinned at scaffold time (work package A1) and recorded in an ADR.

---

## 1. Selection criteria (applied to every component)

| # | Criterion | Why it matters to HUTCH |
|---|---|---|
| C1 | **Open standard or protocol at the boundary** (SQL, Kafka protocol, S3 API, OIDC/OAuth 2.1, OTLP, OpenAPI, MCP) | Can be swapped for a managed service or HUTCH's existing platform |
| C2 | **Neutral governance** (CNCF, Apache, Linux Foundation, PSF, OpenJS) or a clear single-vendor exit path | No single vendor can change the rules |
| C3 | **OSI-approved licence** for anything in the runtime path (no BSL/SSPL/source-available in core) | Legal approval for commercial production use |
| C4 | **Managed equivalent on both AWS and Azure**, and runnable on-prem / Kubernetes | Deploy anywhere (the deployment contract) |
| C5 | **Active security maintenance + LTS** | Patching obligations in a regulated telco |
| C6 | **Proven in regulated industries** and hireable skills | Long-term maintainability |

Where a popular tool fails C2 or C3, the table names it and states why it was not chosen.

---

## 2. Enterprise tech stack

### 2.1 Backend and data

| Layer | Choice (target major) | Standard / protocol | Governance · licence | AWS managed | Azure managed | On-prem / K8s | Not chosen (why) |
|---|---|---|---|---|---|---|---|
| Language | **Python 3.14** | - | PSF · PSF-2.0 | - | - | - | Java/Spring is common in telco BSS. Python is chosen for the AI/ML ecosystem and the deck `[DECK S13]`. Contracts (OpenAPI/AsyncAPI) let HUTCH write extracted modules in any language. |
| API framework | **FastAPI + Pydantic v2 + Uvicorn** (ASGI) | OpenAPI 3.1, JSON Schema 2020-12 | MIT | any container host | any container host | any | Django (heavier, sync-first) |
| Data access | **SQLAlchemy 2 (async) + Alembic + psycopg 3** | SQL | MIT / LGPL | - | - | - | Raw SQL everywhere (no unit-of-work) |
| Python tooling | **uv**, ruff, mypy (strict), pytest | PEP 621 | MIT / Apache | - | - | - | Poetry (slower; uv is now the common standard) |
| Relational DB | **PostgreSQL 18 + pgvector** | SQL | PostgreSQL Licence (BSD-like) | RDS / Aurora PostgreSQL | Azure DB for PostgreSQL Flexible Server | CloudNativePG (CNCF) | Separate vector DB (not needed below tens of millions of vectors) |
| Cache / sessions / rate limits | **Valkey 8** | Redis protocol (RESP) | Linux Foundation · BSD-3 | ElastiCache for Valkey | Azure Managed Redis (protocol-compatible) | Valkey operator | Redis 8+ (tri-licence incl. AGPL/SSPL fails C3 neutrality) |
| Event bus | **Apache Kafka 4 (KRaft, no ZooKeeper)** | Kafka protocol | Apache · Apache-2.0 | Amazon MSK | Event Hubs (Kafka endpoint) | Strimzi (CNCF) | Redpanda (BSL; I suggested it earlier, it fails C3) |
| Schema registry | **Apicurio Registry** | Confluent-compatible API, AsyncAPI | Apache-2.0 | Glue Schema Registry | Event Hubs Schema Registry | Apicurio operator | Confluent Schema Registry (Confluent Community Licence, not OSI) |
| Background jobs | **Postgres-backed job queue (Procrastinate)** behind a `JobQueue` port; Kafka consumers for events | - | MIT | - | - | - | Celery + broker (extra system; still possible as a driver). Temporal only if HUTCH already runs it. |
| Object storage | **S3 API** via `BlobStore` port; **SeaweedFS** locally | S3 API | Apache-2.0 | S3 (+ Object Lock) | Blob Storage (immutable policies) via native driver | SeaweedFS / Ceph RGW | MinIO (community edition archived in 2026) |
| Rules: decision tables | **GoRules ZEN** (JDM) | JSON Decision Model | MIT | - | - | - | Drools (JVM), custom DSL (cost) |
| Rules: cause logic | **Python detector plugins** `rule_id@version` + golden tests | - | - | - | - | - | - |
| Authorization | **OPA 1.x (Rego)** | - | CNCF graduated · Apache-2.0 | (Verified Permissions/Cedar as alt.) | - | OPA | Cedar is a good alternative. OPA is chosen for CNCF maturity and wide K8s/API-gateway use. |
| Identity | **Keycloak 26** (OIDC/OAuth 2.1, RFC 8693 token exchange) | OIDC, OAuth 2.1, SAML | CNCF incubating · Apache-2.0 | Cognito (via OIDC) | Entra ID (via OIDC) | Keycloak operator | Auth0/Okta (SaaS; data residency) |
| Secrets & keys | **OpenBao** (prod-like) behind `Secrets`/`Signer` ports; env/files in dev | - | Linux Foundation · MPL-2.0 | Secrets Manager + KMS | Key Vault | OpenBao / HSM | HashiCorp Vault (BSL since 2023) |
| Crypto | **PyCA `cryptography`** (Ed25519), RFC 8785 JCS | Ed25519, SHA-256 | Apache/BSD | KMS (or envelope key in signer) | Key Vault / Managed HSM | HSM | - |
| PII detection | **Microsoft Presidio** + Sri Lankan recognizers (old/new NIC, 07X mobile, names) | - | MIT | - | - | - | Cloud DLP (sends PII out) |
| Feature flags | **OpenFeature + flagd** | OpenFeature | CNCF | AppConfig (provider) | App Configuration (provider) | flagd | LaunchDarkly (SaaS) |
| Observability | **OpenTelemetry SDK + Collector** → Grafana LGTM (Loki, Grafana, Tempo, Prometheus/Mimir) | OTLP, W3C Trace Context | CNCF · Apache / AGPL (Grafana self-hosted) | CloudWatch + X-Ray via ADOT | Azure Monitor (OTel distro) | Grafana stack | Vendor agents (lock-in) |
| LLM observability | **Langfuse** (self-hosted) | OTel-compatible | MIT core | self-host | self-host | self-host | SaaS-only tools (data leaves) |
| ML | **scikit-learn, LightGBM, UMAP, HDBSCAN, sentence-transformers (BGE-M3)** | - | BSD / MIT | SageMaker (optional) | Azure ML (optional) | any | - |
| Event / API formats | **CloudEvents 1.0, RFC 9457 problem details, TMF Open API shapes** | - | CNCF / IETF / TM Forum | - | - | - | - |

### 2.2 Frontend

| Layer | Choice | Why |
|---|---|---|
| Language / UI | **TypeScript + React** | Industry default; largest hiring pool |
| Framework | **Next.js 16** (App Router, `output: "standalone"`) | SSR for the verify page and BFF route handlers. Standalone output runs on any Node host or container, not only Vercel. |
| Runtime | **Node.js 24 LTS** | LTS support window |
| Components | **shadcn/ui on Radix primitives + Tailwind CSS** | Accessible primitives (WCAG), code owned in-repo (no vendor runtime) |
| Data fetching | **TanStack Query** + SDK generated from OpenAPI (`openapi-typescript`) | Typed end to end |
| i18n | **next-intl** (ICU messages) with si/ta/en catalogues; Noto Sans Sinhala / Tamil | Correct plurals and number formats |
| Embeddable widget | Web Component wrapper over the same React component (`<clarity-why>`) | Works in hutch.lk, the app WebView and the MCP Apps card |
| Monorepo tooling | **pnpm + Turborepo** | Fast, deterministic workspaces |
| Testing | Vitest, Playwright, axe-core | Unit, E2E, accessibility |

### 2.3 Runtime profiles
Every component above is the **production** choice. Daily development runs the `lite` profile (Python only, in-memory and in-process drivers), and the real components run in the `full` profile and the CI integration lane. Driver matrix and rules: [18 §2.3](18-build-blueprint.md), ADR-0027.

### 2.4 Delivery and supply chain (GitHub)

| Concern | Choice |
|---|---|
| CI/CD | **GitHub Actions** (reusable workflows, OIDC to clouds, environments with required reviewers) |
| Dependency updates | **Renovate** (or Dependabot), grouped, with auto-merge for patch updates that pass CI |
| SAST | **CodeQL** (free for public repos; private repos need GitHub Advanced Security) + **Semgrep CE** |
| Secrets scanning | GitHub secret scanning + **gitleaks** in CI |
| Containers | OCI images, non-root, read-only rootfs, slim/distroless bases; **Trivy** scan; **Syft** SBOM (SPDX/CycloneDX) |
| Signing & provenance | **cosign** (Sigstore) keyless signing + GitHub artifact attestations (SLSA provenance) |
| Repo posture | Branch protection, CODEOWNERS, signed commits on money-path dirs, **OpenSSF Scorecard** |
| IaC | **OpenTofu** (Terraform-compatible HCL; HUTCH can run either), **Helm** charts, **kind** in CI to prove the chart |
| API quality | Spectral (OpenAPI lint), oasdiff (breaking-change check), Schemathesis (fuzz), Pact (contracts) |
| Load / security tests | k6, OWASP ZAP |
| Docs | MkDocs Material, ADRs in MADR format, C4 diagrams in Mermaid |

---

## 3. Is this "AWS-like modular"?

**Yes, in the way that matters.** The design follows the same principles AWS recommends (Well-Architected Framework, and Prescriptive Guidance for decomposing systems). It uses portable components instead of AWS-only services, so HUTCH can run it on AWS, Azure or its own data centre.

| AWS idea | How Hutch Clarity does it |
|---|---|
| Service boundaries ("two-pizza" teams, each owning its data) | Each module owns its Postgres schema, API and events. No shared tables. |
| Start simple, split later (strangler-fig pattern) | Modular monolith first. A module is extracted by rebinding its `public.py` facade to an HTTP client. |
| Layered security (edge → identity → authorization → data) | WAF/gateway → OIDC/OTP → OPA → row-level security → PII vault → audit |
| Event-driven decoupling (EventBridge/SNS/SQS) | Outbox → Kafka → idempotent consumers with DLQs |
| Managed building blocks | Every infrastructure port has an AWS and an Azure managed driver (§2.1) |

**Well-Architected pillars mapping:**

| Pillar | Evidence in the design |
|---|---|
| Operational excellence | GitOps, IaC, runbooks, OTel everywhere, feature flags and kill switches |
| Security | Deny-by-default, OPA, RLS, MFA + step-up, PII masking before AI, signed images, SBOM, key isolation |
| Reliability | Outbox, idempotency, retries + DLQ, circuit breakers on adapters, graceful degradation to templates |
| Performance efficiency | Stateless scale-out, Kafka keyed by `subscriber_ref`, cache tiers, async workers |
| Cost optimization | Rules/templates/cache before any LLM; cheap model by default; reasoning model only when needed |
| Sustainability | Fewer model calls, paperless receipts, right-sized AI `[DECK S15]` |

---

## 4. LLM strategy: Gemini + Groq free tiers now, HUTCH's models later

### 4.1 Principles
1. **Logical model roles, not model names, in code.** Code asks for `fast-text` or `reason`; config maps each role to a provider and model. HUTCH changes providers by editing config.
2. **One `ModelProvider` port, OpenAI-compatible wire format by default.** Groq is OpenAI-compatible, Gemini offers an OpenAI-compatible endpoint, and vLLM and Azure OpenAI speak it too. Native drivers are used only where a feature needs them (e.g., Gemini TTS).
3. **The answer ladder from the deck stays:** templates → exact cache → semantic cache → cheap model → reasoning model `[DECK S14]`. Most traffic never reaches a model.
4. **Every call goes through the AI gateway:** masking enforced, token budget checked, rate limit respected, Langfuse trace written, verifier applied.

### 4.2 Role → model routing (prototype)

| Role | Used for | Primary | Fallback 1 | Final fallback | Why |
|---|---|---|---|---|---|
| `fast-text` (non-reasoning) | Customer explanation from FACTS (si/ta/en), short replies, reply drafts for agents | **Gemini Flash-Lite** (`gemini-3.5-flash-lite`) | Groq `openai/gpt-oss-20b` (English only) | Approved template | Best si/ta quality among free options; cheapest tier |
| `extract` | Intent + slots JSON from si/ta/en/Singlish text | **Gemini Flash-Lite** (JSON schema output) | Groq `openai/gpt-oss-20b` (structured output) | Rule-based keyword intents + ask a clarifying button | Structured output, multilingual |
| `reason` | Complex or unusual cases, staff case summary, shift handover, cluster labelling, rule-proposal drafts | **Groq `openai/gpt-oss-120b`** (`reasoning_effort` medium) | **Gemini Flash** (`gemini-3.8-flash`, thinking budget capped) | Hand off to staff | Strong reasoning, very fast, no training on data by contract |
| `judge` | Sampled faithfulness check (LLM-as-judge) | Groq `openai/gpt-oss-20b` | Gemini Flash-Lite | Skip (deterministic verifier still runs) | Fast and cheap; never the only check |
| `guard` | Prompt-injection classifier on inputs | Groq Llama Prompt Guard (**preview**) | Heuristic rules | Rules only | High free quota; preview, so never the only defence |
| `embed` | RAG, Autopsy clustering | **Self-hosted BGE-M3** (CPU is fine at prototype volume) | Gemini Embedding (preview) | - | No data leaves; free; portable |
| `stt` | Sinhala/Tamil voice notes | Groq `whisper-large-v3` | Gemini Transcribe (`gemini-3.5-transcribe`) | Ask the customer to type | Sinhala Whisper quality is weak, so measure WER and pick the per-language winner |
| `tts` | Spoken replies | Gemini Flash-Lite TTS (`gemini-3.8-flash-lite-tts`) | - | Text only | si/ta voice availability **to verify** in Phase B4 |

Model IDs above reflect the providers' model pages as of 2026-10-01 and change often. They live in `config/ai/models.yaml`, never in code.

```yaml
# config/ai/models.yaml (illustrative)
roles:
  fast-text:
    chain: [gemini/gemini-3.5-flash-lite, groq/openai/gpt-oss-20b, template]
    max_output_tokens: 400
    languages: {si: [gemini], ta: [gemini], en: [gemini, groq]}
  reason:
    chain: [groq/openai/gpt-oss-120b, gemini/gemini-3.8-flash, handoff]
    params: {reasoning_effort: medium}
    max_output_tokens: 1500
budgets:
  per_session_tokens: 12000
  daily_tokens: {gemini: 900000, groq: 550000}   # kept under free-tier daily limits
priorities: [customer_live, staff_live, batch]     # batch waits when quota is low
```

### 4.3 Free-tier constraints and the engineering they force

| Provider | Free-tier facts (check live) | Consequence |
|---|---|---|
| **Groq** | Per-model limits, organisation-wide. `gpt-oss-120b/20b`: **30 RPM, 1K RPD, 8K TPM, 200K TPD**. Whisper: 20 RPM, 2K RPD. Prompt Guard: 14.4K RPD. Cached tokens don't count. | 8K TPM means about one large staff summary per minute. Keep prompts tight; send heavy batch work to Gemini or schedule it. |
| **Gemini** | Pro models left the free tier on 2026-04-01; Flash and Flash-Lite remain. Exact RPM/RPD are shown only in AI Studio (third-party reports: roughly 10–15 RPM and 1–1.5K RPD per model). | Treat each model as about 1K calls/day. |

Engineering requirements this creates (all in the AI gateway, B4):
1. **Quota-aware token buckets** per provider and model, mirroring the published limits, so the gateway never triggers a 429 storm.
2. **Priority queue:** live customer turns > live staff turns > batch (Autopsy, Foresight).
3. **Automatic fallback** down the role chain on 429, timeout, or verifier failure.
4. **Record/replay cassettes** for CI. Tests never call live models (deterministic and free); a nightly smoke run uses the live quota.
5. **Demo mode:** pre-warmed caches and templates so a live demo never depends on quota.
6. **Usage ledger:** tokens per role, model and journey. This produces the measured numbers the guidelines require (§6.2) instead of assumptions.

Rough prototype capacity: about 3–5K LLM calls/day across both providers. With 33–50% of interactions needing no LLM, that is about 2–4K interactions/day. This is plenty for development, demos and judging.

### 4.4 Data protection on free tiers (non-negotiable)

| Provider | Policy | Rule for this project |
|---|---|---|
| **Gemini (unpaid)** | Prompts and responses **may be used to improve Google products and reviewed by humans**. Google advises against sending sensitive or personal data. | **Synthetic data only**, always PII-masked. Never real HUTCH data on the free tier. Real data requires the paid tier, Vertex AI, or HUTCH's own models. |
| **Groq** | No training on customer data (contractual). Inputs/outputs may be kept up to 30 days for abuse/reliability unless **Zero Data Retention** is enabled. | **Enable ZDR** in the Groq console on day 1. Still synthetic + masked only. |

State this in the AI usage declaration and Known Limitations. It turns a free-tier risk into evidence of good governance.

### 4.5 Production path (when HUTCH buys)

The same roles, with new config only:

| Option | `fast-text` / `extract` | `reason` | Notes |
|---|---|---|---|
| Google enterprise | Gemini Flash-Lite on **Vertex AI** (DPA, regional) | Gemini Flash / Pro | Same model family the prototype was tuned on |
| Microsoft | Azure OpenAI / AI Foundry small model | Azure reasoning model | If HUTCH is on Azure |
| AWS | Bedrock small model | Bedrock reasoning model | If HUTCH is on AWS |
| Self-hosted (data stays in HUTCH) | vLLM serving an open-weight model (e.g., gpt-oss-20b, Gemma, Qwen class) | vLLM gpt-oss-120b class | GPU cost vs volume per [§37](15-cost-scale-failure-kpi.md) |

Switching providers requires re-running the **evaluation suite per language** ([§12.7](08-ai-architecture.md)) as a release gate, because Sinhala/Tamil quality varies a lot between models.

### 4.6 AI disclosure table (Guidelines §6.1), prototype values

| Item | Value |
|---|---|
| Providers | Google (Gemini API, free tier); Groq (GroqCloud, free tier); self-hosted BGE-M3 embeddings |
| Models | See §4.2 (IDs pinned in `config/ai/models.yaml` at release) |
| Purpose | Language only: extraction, explanation, summaries, drafting, clustering labels, simulation personas. **Never** causes, amounts, eligibility or actions. |
| Calls per journey | Structured Why?: 0–1. Free-text dispute: 2 (+0.2 judge). Staff summary: 2. Zero-contact: 0. **Measured values will replace these from the usage ledger.** |
| Tokens | Measured per role in Langfuse; assumptions in [§37](15-cost-scale-failure-kpi.md) until then |
| RAG | Yes: catalogue, T&C, Gazette 2316/14, help content (sample documents in the prototype) |
| Fallback | Role chain → templates → human handoff |

---

## 5. Impact on chapters 01–16 (can we keep them?)

**Yes. Chapters 01–16 stay as the enterprise plan.** Their problem analysis, requirements, journeys, security model, MCP safety levels, receipts, risks and KPIs remain valid. Some *technical choices* inside them were superseded by chapters 18–20 and **were updated in plan v1.1** (record: [CHANGES.md](CHANGES.md)):

| Chapter | Status | What changes |
|---|---|---|
| 01 Executive summary & problem | ✅ Keep | Update the "LLM stance" line in the README |
| 02 Solution capabilities | ✅ Keep | - |
| 03 Requirements, personas, journeys | ✅ Keep | Add admin persona + platform/security admin requirements; mark which FRs the prototype builds (per 18 §3.1) |
| 04 Enterprise architecture | ✅ Updated (v1.1) | Layer table → 18 §2.2 layers; T1 (Celery → Postgres job queue), T3 (YAML DSL → Python detectors + ZEN), T6 (providers), Redpanda/MinIO/Vault notes |
| 05 Architecture diagrams | ✅ Updated (v1.1) | Rename components (Valkey, Kafka KRaft, SeaweedFS/S3); add deployables view from 18 §4 |
| 06 Integration & TMF | ✅ Keep | Add `hutch-sim` as the named mock driver set |
| 07 MCP | ✅ Updated (v1.1) | 2026-07-28 spec: stateless, OAuth 2.1 resource server, RFC 8707, token exchange (no passthrough); external MCP clients; MCP Apps UI |
| 08 AI architecture | ✅ Updated (v1.1) | Model tiers → roles + Gemini/Groq routing (§4); free-tier data policy |
| 09 Rules, decision, receipts | ✅ Updated (v1.1) | Rule representation → Python detectors + ZEN decision tables; OPA kept for authorization; config override model (18 §8) |
| 10 Data, API, events | ✅ Updated (v1.1) | Schema-per-module and DB roles; Apicurio registry |
| 11 Security, privacy, audit | ✅ Updated (v1.1) | Add MCP threats, RLS, separation-of-duties matrix (18 §5.4), free-tier AI data rule |
| 12 Platform, DevOps, testing | ✅ Updated (v1.1) | Stack table → §2; GitHub Actions pipeline; record/replay AI tests |
| 13 Delivery plan | ✅ Updated (v1.1) | Keep as the **HUTCH production programme**; add a pointer that the **prototype build** schedule is 18 §14 |
| 14 Risk, pilot, operations | ✅ Keep | Add risks: free-tier quota/policy, Sinhala STT quality |
| 15 Cost, scale, failure, KPI | ✅ Updated (v1.1) | Add free-tier capacity (§4.3); cost formula from the measured usage ledger |
| 16 Gap, submission, repo | ✅ Updated (v1.1) | Repo structure → 18 §2/§4 layout; fill the AI declaration from §4.6 |

---

[← 18-build-blueprint.md](18-build-blueprint.md) · [← Plan index](README.md) · [20-policy-change-management.md →](20-policy-change-management.md)

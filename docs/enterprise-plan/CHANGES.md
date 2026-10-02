# Enterprise Plan - Change Record

[← Plan index](README.md)

This plan is a **versioned baseline**. Once the team starts building, it changes only through this record, so every developer works from the same intent.

## How to change the plan

1. **Decide first.** A change to architecture, technology, scope, security or a module boundary needs an **ADR** in `docs/adr/` (status `Proposed` → `Accepted`). Wording fixes and clarifications don't.
2. **Edit the affected chapters** in the same pull request as the ADR (or right after it is accepted).
3. **Add an entry below** with the new plan version, date, ADR link, chapters touched and a one-line summary per change.
4. **Update the living docs that depend on it.** Usually that means `ARCHITECTURE.md` and the affected `MODULE.md` files (see the sync matrix in `AGENTS.md`).
5. **Bump the version** in [README.md](README.md): minor (1.x) for content changes, major (2.0) when the architecture baseline changes.

**Precedence when documents disagree:** accepted ADR > `ARCHITECTURE.md` (current as-built state) > plan chapters 18–20 > plan chapters 01–16. A disagreement is a bug: fix it in the same PR that found it.

---

## v1.6 - 2026-10-02

| Area | Change | Chapters |
|---|---|---|
| Runtime profiles | New 19 §2.3.1 "Drivers built so far": the port, driver and parity suite for persistence (B02) and the event bus (B03), how to run the `full` drivers (`make up-full`, `make test-full`), and the Kafka driver's design. Records that Kafka blocks a whole partition where the in-process driver blocks one subject, and that confluent-kafka (Apache-2.0 over BSD-2 librdkafka) is an optional extra rather than a core dependency | 19 |

## v1.5 - 2026-10-02

| Area | Change | Chapters |
|---|---|---|
| Agentic assistant | Flows as versioned state machines, bounded agent step with tool allowlists and limits, RAG with mandatory citations, guardrails, per-language evaluation (ADR-0030) | 22 (new) |
| Backlog | Per-module issues with acceptance tests and Definition of Done, in waves from the platform baseline upward | docs/backlog |

## v1.4 - 2026-10-02

| Area | Change | Chapters |
|---|---|---|
| Module interaction | Calls through `public.py` for answers, outbox events for side effects; declared dependency map; event catalogue; delivery rules; first event-driven flow; R2a platform baseline (ADR-0029) | 21 §11 (new) |
| Migration status | R0 done (acceptance suite); D7 fixed (`/mock/*` routes refused in `prod`) | 21 §3, §7 |

## v1.3.1 - 2026-10-02

| Area | Change | Chapters |
|---|---|---|
| Migration status | R1 done; R2 and R5 started by the team (SQL-backed `full` profile, Next.js apps) after their commits were merged into `dev` | 21 §7 |

## v1.3 - 2026-10-02 (merged plan)

| Area | Change | Chapters |
|---|---|---|
| Merge | The team's v1.1 audit plan (chapters 01–17, §1–§52) and the v1.2 line ("Plan v1") are now one plan. v1.2 chapters 17–19 became 18–20; its edits to chapters 03–16 were ported. | all |
| Migration | New chapter 21: keep the proven logic, rewrite the structure, replace infrastructure; defects D1–D6; steps R0–R7; schedule | 21 (new) |
| Runtime model | Containers for the money path, stream detectors, adapters and signer; serverless allowed for verify, rendering, notifications, webhooks, batch jobs and the stateless MCP server; Knative/KEDA for serverless behaviour on HUTCH's own platform (ADR-0028) | 21 §5, 04 T17, 12 |
| Microservices | Modular monolith first, satellites second, hot modules extracted on defined triggers; extraction is a deployment change (facade → HTTP client) | 21 §6 |
| Rules | YAML rule packs stay (they work and "rules are data"); parameters move to the policy store; outcome matrix becomes a ZEN table; OPA for authorization (ADR-0026, supersedes ADR-0015) | 09, 04 T3 |
| Profiles | `lite` needs **only Python** (in-memory drivers); `full` runs the real components (ADR-0027, supersedes ADR-0024) | 21 §9, 18 §2.3 |
| ADRs | One sequence: the team's ADR-0001…0010 kept; the v1.2 ADRs renumbered 0011…0024; new 0025…0028 | docs/adr |
| Requirements, threats, risks | FR-GOV-06…08, FR-ADM-01…02, FR-MCP-02; TH14–TH19; R24–R28 | 03, 11, 14 |

## v1.2 - 2026-10-01

| Area | Change | Chapters |
|---|---|---|
| Developer experience | Runtime profiles `lite` / `full` / `prod` chosen by config; daily dev needs only Python, Node and PostgreSQL; driver parity suites; real drivers in a CI lane (I0 to I3); local database and secrets workflow ([ADR-0024](../adr/0024-runtime-profiles.md)) | 18 §2.3 to §2.5, §12, §14; 04 T14; 12 §22.1; 19 §2.3 |
| Governance | No em dash anywhere; one author per commit, no attribution; short bullet commit messages (AGENTS.md I18, I19, §10.1) | repo docs |

## v1.1 - 2026-10-01

| Area | Change | Chapters |
|---|---|---|
| Build approach | Added the build blueprint: permanent baseline, module protocol, layer rules, deployables, identity, UI connections, data flow, notifications, MCP build, dependency graphs and the prototype Gantt chart | 18 (new) |
| Tech stack | Selection criteria (open standards, neutral governance, OSI licences, AWS + Azure managed equivalents). Valkey instead of Redis; Apache Kafka KRaft + Apicurio instead of Redpanda/Confluent; SeaweedFS instead of MinIO; OpenBao instead of HashiCorp Vault; OpenTofu; Python 3.14, PostgreSQL 18, Node 24 LTS, Next.js 16 | 19 (new), 04, 05, 12 |
| Deployment shape | Modular monolith with a schema per module + separately deployed services (MCP, signer, AI gateway, channel gateway, workers, hutch-sim) instead of ~13 microservices; deployment contract instead of a Kubernetes baseline | 04 (T11, T14), 16 §43 |
| AI | Logical model roles; Gemini + Groq free tiers for the prototype (synthetic, masked data only; Groq ZDR); HUTCH's models later by config; semantic cache on pgvector | 08, 04 (T6, T7, T15), 15, 16 |
| Rules | Python detector plugins + manifests + ZEN decision tables; OPA kept for authorization | 09, 04 (T3) |
| Policy change | One enterprise lifecycle for every kind of policy change (catalogue, legal text, parameters, tables, logic, wording, switches, access) | 20 (new), 03, 09, 10, 11, 14 |
| MCP | 2026-07-28 spec: stateless core, OAuth 2.1 resource server, RFC 8707, token exchange (no passthrough), external MCP clients, MCP Apps UI | 07, 11 |
| Requirements | Admin persona; FR-GOV-04…06, FR-ADM-01…02, FR-MCP-02 | 03 |
| Security | Row-level security, MCP threats, free-tier data rule, policy-change threat (TH14–TH17) | 11 |
| Risks | R24 free-tier quotas, R25 policy change, R26 documentation drift | 14 |
| Delivery | Chapter 13 scoped as the HUTCH production programme; prototype schedule moved to 18 §14 | 13, 17 |
| Repository | New structure, living documentation rules (AGENTS.md, ARCHITECTURE.md, MODULE.md, walkthroughs, devlog) | 16 |

## v1.0 - 2026-10-01
Initial draft: chapters 01–16 derived from the 17-slide deck and the submission guidelines.

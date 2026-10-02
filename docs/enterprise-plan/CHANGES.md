# Enterprise Plan - Change Record

[← Plan index](README.md)

This plan is a **versioned baseline**. Once the team starts building, it changes only through this record, so every developer works from the same intent.

## How to change the plan

1. **Decide first.** A change to architecture, technology, scope, security or a module boundary needs an **ADR** in `docs/adr/` (status `Proposed` → `Accepted`). Wording fixes and clarifications don't.
2. **Edit the affected chapters** in the same pull request as the ADR (or right after it is accepted).
3. **Add an entry below** with the new plan version, date, ADR link, chapters touched and a one-line summary per change.
4. **Update the living docs that depend on it.** Usually that means `ARCHITECTURE.md` and the affected `MODULE.md` files (see the sync matrix in `AGENTS.md`).
5. **Bump the version** in [README.md](README.md): minor (1.x) for content changes, major (2.0) when the architecture baseline changes.

**Precedence when documents disagree:** accepted ADR > `ARCHITECTURE.md` (current as-built state) > plan chapters 17–19 > plan chapters 01–16. A disagreement is a bug: fix it in the same PR that found it.

---

## v1.2 - 2026-10-01

| Area | Change | Chapters |
|---|---|---|
| Developer experience | Runtime profiles `lite` / `full` / `prod` chosen by config; daily dev needs only Python, Node and PostgreSQL; driver parity suites; real drivers in a CI lane (I0 to I3); local database and secrets workflow ([ADR-0014](../docs/adr/0014-runtime-profiles.md)) | 17 §2.3 to §2.5, §12, §14; 04 T14; 12 §22.1; 18 §2.3 |
| Governance | No em dash anywhere; one author per commit, no attribution; short bullet commit messages (AGENTS.md I18, I19, §10.1) | repo docs |

## v1.1 - 2026-10-01

| Area | Change | Chapters |
|---|---|---|
| Build approach | Added the build blueprint: permanent baseline, module protocol, layer rules, deployables, identity, UI connections, data flow, notifications, MCP build, dependency graphs and the prototype Gantt chart | 17 (new) |
| Tech stack | Selection criteria (open standards, neutral governance, OSI licences, AWS + Azure managed equivalents). Valkey instead of Redis; Apache Kafka KRaft + Apicurio instead of Redpanda/Confluent; SeaweedFS instead of MinIO; OpenBao instead of HashiCorp Vault; OpenTofu; Python 3.14, PostgreSQL 18, Node 24 LTS, Next.js 16 | 18 (new), 04, 05, 12 |
| Deployment shape | Modular monolith with a schema per module + separately deployed services (MCP, signer, AI gateway, channel gateway, workers, hutch-sim) instead of ~13 microservices; deployment contract instead of a Kubernetes baseline | 04 (T11, T14), 16 §43 |
| AI | Logical model roles; Gemini + Groq free tiers for the prototype (synthetic, masked data only; Groq ZDR); HUTCH's models later by config; semantic cache on pgvector | 08, 04 (T6, T7, T15), 15, 16 |
| Rules | Python detector plugins + manifests + ZEN decision tables; OPA kept for authorization | 09, 04 (T3) |
| Policy change | One enterprise lifecycle for every kind of policy change (catalogue, legal text, parameters, tables, logic, wording, switches, access) | 19 (new), 03, 09, 10, 11, 14 |
| MCP | 2026-07-28 spec: stateless core, OAuth 2.1 resource server, RFC 8707, token exchange (no passthrough), external MCP clients, MCP Apps UI | 07, 11 |
| Requirements | Admin persona; FR-GOV-04…06, FR-ADM-01…02, FR-MCP-02 | 03 |
| Security | Row-level security, MCP threats, free-tier data rule, policy-change threat (TH14–TH17) | 11 |
| Risks | R24 free-tier quotas, R25 policy change, R26 documentation drift | 14 |
| Delivery | Chapter 13 scoped as the HUTCH production programme; prototype schedule moved to 17 §14 | 13, 17 |
| Repository | New structure, living documentation rules (AGENTS.md, ARCHITECTURE.md, MODULE.md, walkthroughs, devlog) | 16 |

## v1.0 - 2026-10-01
Initial draft: chapters 01–16 derived from the 17-slide deck and the submission guidelines.

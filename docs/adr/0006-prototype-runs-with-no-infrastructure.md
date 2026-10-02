# 0006 - The prototype runs with no infrastructure, behind swappable ports

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | `docs/improvement-plan.md` D3, D4, S1, S3; alternative design ADR-0014 |

> **Refined by ADR-0027** (2026-10-02): "no infrastructure" becomes the `lite` profile, and the real components run in the `full` profile behind the same ports.

## Context
The hackathon guidelines require a reviewer to clone the repository and run it.
Every component added - a broker, a cache, an identity server, a Node toolchain
- is a setup step and a way the live demo fails.

The production design (plan §21) is Kafka, Valkey, PostgreSQL, Keycloak, OPA
and Next.js, and that remains correct for production.

## Decision
The default `demo` profile runs entirely in memory and needs only Python. The
UI is static HTML and vanilla JavaScript served by the same FastAPI process,
consuming only the public `/v1` API. Infrastructure sits behind ports with
driver parity suites, so a real driver is added without touching domain code.

A profile chooses **drivers only**. The outbox, idempotency keys, `Money`, the
clock, permissions and correlation IDs exist in every profile: the prototype
skips servers, never seams. `CLARITY_PROFILE` is read in exactly one place, the
composition root.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Full production stack now | Heavy setup, no demo value, more to fail on demo day |
| SQLite as the local database | Schemas, row-level security and pgvector differ from PostgreSQL, so local behaviour would not match production. If persistence lands, it is PostgreSQL. |
| Next.js front end | Needs a Node toolchain and a second server; the pages use only the public API, so swapping them later is contained |

## Consequences
Nothing survives a restart, and the API has no authentication. Both are
recorded in `docs/submission/KNOWN_LIMITATIONS.md`. Persistence and identity
are Phases 3 and 5 of the improvement plan.

## Compliance
`tests/contract/test_port_parity.py` holds one suite per port that every driver
must pass. `tests/unit/test_api.py::test_only_the_composition_root_reads_the_profile`.

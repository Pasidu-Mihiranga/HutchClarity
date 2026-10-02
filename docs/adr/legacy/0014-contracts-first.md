# 0014 - Contracts first

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
Without durable contracts, modules invent ad-hoc shapes and the frontends drift from the API and event bus.

## Decision
Treat `contracts/` as the source of truth before implementation: OpenAPI (`contracts/openapi/v1.yaml`), AsyncAPI (`contracts/asyncapi/events.yaml`), permissions catalogue (`contracts/permissions/catalogue.yaml`), and JSON Schema for shared payloads. Code and tests consume generated or hand-checked stubs from these files.

## Consequences
PRs that change behaviour without updating contracts are rejected. CI may later add contract lint and breaking-change checks. Runtime profiles (lite/full) do not change contract shapes — only drivers.

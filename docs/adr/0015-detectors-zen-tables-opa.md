# 0015 - Python detectors + ZEN decision tables for rules; OPA for authorization

| Field | Value |
|---|---|
| Status | Superseded by 0026 |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | enterprise-plan/09 §13–14; 04 T3 |

> **Superseded.** Python detector plugins were not adopted: the working YAML rule packs stay (ADR-0001). ZEN decision tables for outcomes and OPA for authorization carry forward in ADR-0026.

## Context
Cause detection is temporal evidence logic; outcome thresholds change often and must be business-editable; authorization needs a policy engine. A custom YAML DSL would be costly and still not editable by business users.

## Decision
Cause logic = versioned Python detector plugins with manifests (pure functions of snapshot + params). Outcome matrix, caps and thresholds = GoRules ZEN decision tables (JDM). Authorization and MCP access = OPA/Rego. All released as signed, versioned bundles.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Custom YAML DSL | Build cost; limited expressiveness |
| Rego for outcomes | Not business-editable; awkward for tables |
| Drools | JVM dependency |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `enterprise-plan/CHANGES.md`.

## Compliance
Golden tests per rule version; replay must reproduce a decision exactly from snapshot + versions.

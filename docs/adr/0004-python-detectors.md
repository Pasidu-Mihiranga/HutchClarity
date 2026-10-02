# 0004 - Python detectors for cause logic

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
Cause detection is temporal evidence logic. A custom YAML DSL would be costly and still weak for timelines.

## Decision
Cause logic = versioned Python detector plugins (pure functions of snapshot + params) with manifests. Outcome matrices and caps use decision tables (ZEN/JDM) where business-editable. Authorization stays on the Policy port (ADR-0005).

## Consequences
Golden tests per rule version. Replay reproduces a decision from snapshot + versions. Detectors ship as signed bundles.

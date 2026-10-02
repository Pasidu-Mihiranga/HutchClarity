# 0026 - Rules: YAML cause packs, ZEN outcome tables, OPA for authorization

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Deciders | Architecture (merged plan v1.3); team to ratify |
| Plan references | enterprise-plan/09 §13-14; 04 T3 |

## Context
Two designs existed: YAML rule packs with a predicate engine (built, ADR-0001) and Python detectors with ZEN tables (designed, ADR-0015). Cause logic must be data that compliance can review and publish without a deploy; outcome thresholds must be editable by Finance and CX; authorization needs a policy engine.

## Decision
Cause detection stays in versioned YAML rule packs. Their numeric parameters (confidence base and adjustments, windows) move to the scoped policy store. The outcome matrix becomes a GoRules ZEN decision table evaluated in process, with every parameter resolved from the same config snapshot. OPA evaluates authorization (approvals, MCP access) in the `full` and `prod` profiles; the Python permission checks remain the `lite` driver behind the same interface.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Python detector plugins | Logic in code turns a rule change into a deploy; the YAML engine already exists and is tested |
| Outcomes in Python only | Not editable by business owners; harder to replay with a candidate table |

## Consequences
The migration plan (chapter 21) and `ARCHITECTURE.md` follow this decision. Changing it needs a superseding ADR and a plan update via `docs/enterprise-plan/CHANGES.md`.

## Compliance
Golden tests per pack version; decision-table tests per outcome row; a parity suite runs the same authorization cases against the Python driver and OPA; no constant in the tool layer may shadow a policy value.

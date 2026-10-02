# 0020 - Customer notifications use approved templates only

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | enterprise-plan/18 §9 |

## Context
LLM-written messages to customers could promise refunds or leak data; WhatsApp requires approved templates outside the 24-hour window.

## Decision
The notifications module sends only versioned templates with validated parameters, routed by preference and consent, idempotent per (event, recipient, template), with fallback channels and delivery tracking.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| LLM free-text messages | Unverifiable promises; compliance risk |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `enterprise-plan/CHANGES.md`.

## Compliance
Notification API rejects free text; template changes follow the policy lifecycle (ADR-0021).

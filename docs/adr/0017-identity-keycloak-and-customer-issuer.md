# 0017 - Identity: Keycloak for staff/admin/machines, Clarity issuer for customers

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Deciders | Architecture planning (plan v1.1); team to ratify at kickoff |
| Plan references | enterprise-plan/18 §5 |

## Context
Customers authenticate by OTP, app token exchange, WhatsApp step-up or network MSISDN; staff need SSO + MFA; machines and MCP clients need OAuth 2.1.

## Decision
Keycloak realm `clarity-staff` (federates HUTCH AD/Entra in production) for staff, admins, services and MCP clients. The `iam` module issues short-lived customer tokens (`sub = subscriber_ref`) behind an interface HUTCH's customer IdP can replace. OPA decides permissions; maker ≠ checker enforced.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Keycloak for customers too | No built-in SMS OTP; customer identity in production belongs to HUTCH anyway |
| SaaS IdP | Data residency |

## Consequences
Builds follow this decision from the baseline onward. Changing it requires a new ADR that supersedes this one and a plan update via `enterprise-plan/CHANGES.md`.

## Compliance
Permission matrix tests in OPA; step-up required for approvals above threshold.

# 0010 - Customer notifications are template-only

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |

## Context
LLM free-text to customers can promise refunds or leak data. WhatsApp requires approved templates outside the 24-hour window.

## Decision
The notifications module sends only versioned templates with validated parameters, routed by preference and consent, idempotent per (event, recipient, template), with fallback channels and delivery tracking.

## Consequences
Notification API rejects free text. Template changes follow the policy artefact lifecycle. Compliance can audit every message against a template version.

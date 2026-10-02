# 0007 - Confirmation tokens are minted and spent server-side

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | `docs/enterprise-plan/10-data-api-events.md` §17.2; `docs/improvement-plan.md` |

## Context
Plan §17.2 shows `POST /v1/cases/{id}/actions` carrying an
`X-Confirmation-Token` header, minted by the channel. That assumes the channel
is a trusted service holding its own credentials.

## Decision
The authenticated tap **is** the confirmation. `confirm_and_execute` mints the
token and spends it inside the same request, so it never travels to a client.
Amounts are never accepted from a client either: they come from the decision
record.

This is a tightening of §17.2, not a departure from it: a token that never
exists outside the server cannot be captured or replayed.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Return the token to the client | Creates a capturable, replayable credential for no benefit while the channel and the API are the same process |

## Consequences
When channels become separate services (WhatsApp, SMS), they will need their
own confirmation flow. The token service already supports it; only the route
changes.

## Compliance
`tests/unit/test_api.py` asserts a staff case cannot be confirmed as a
customer, a one-tap case cannot self-authorise as auto-fix, and a plan cannot
execute twice.

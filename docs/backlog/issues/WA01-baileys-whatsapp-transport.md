# [WA01] Baileys WhatsApp transport adapter

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `channel-gateway` |
| Priority | P1 |
| Depends on | DEP01, CD01, N02, C01, N01 |
| Plan | 09 §9.7; 21 §7 R4 |
| Labels | `wave:w5`, `area:channel-gateway`, `priority:p1`, `type:feature` |

## Scope

Add a Node.js/TypeScript Baileys transport that normalizes one-to-one messages,
signs the existing webhook contract and sends the exact gateway response. It
must contain no Clarity rules, amount authority, confirmation tokens or LLM.
Auth state is persistent, pairing is operator-only and the service is disabled
by default.

## Acceptance tests

- DEP01 and CD01 are verified before implementation begins.
- Mocked socket tests cover filtering, identity, replay, signing, exact response,
  proactive notification, delivery state, voice fallback and secret redaction.
- Core Clarity stays healthy with WhatsApp disabled.
- A live synthetic direct-message journey and auth persistence are verified.

GitHub: #59. Status: blocked on DEP01 and CD01.

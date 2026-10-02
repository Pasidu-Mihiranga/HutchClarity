# conversation - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.conversation`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); added by the team on 2026-10-02 (commit `2bd8fc9`), ported into the layered layout |
| Files | `intents.py`, `intent_routes.py`, `service.py`, `suggestions.py`, `public.py` |

## 1. Purpose
Customer chat intake for the immersive "Clarity chat": detect language (Sinhala, Tamil, English), classify intent with deterministic keyword rules, route each intent to the right journey (dispute, explain, safeguard, pack help, human handoff), and offer contextual suggestions from the case's evidence snapshot. No language model is involved.

## 2. Public surface (`public.py`)
`build_suggestions`, `extract_intake`, `handle_turn`, `signals_from_snapshot`, `suggest_for_snapshot`.

## 3. Used by
`clarity.interfaces.http` (chat routes and suggestions).

## 4. Depends on
| Package | Through |
|---|---|
| (standard library only) | - |

## 5. Data owned
None. Turns are stateless; case state lives in `modules.case`.

## 6. Invariants
- Customer text is a hint, never evidence (I2): intake only selects a route; causes and amounts still come from rule packs and the decision policy.
- Handoff keywords always win, so a customer asking for a person is never kept in automation.

## 7. Migration status (enterprise-plan 21)
Keyword rules in code. Target: intents and phrases as versioned content under the policy lifecycle (plan 20), and the `extract` model role behind the AI gateway as an optional assist (plan 19 §4), with the keyword rules as the fallback.

## 8. Tests
- `backend/tests/unit/test_conversation_chat.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-kodee-clarity-chat.md` | Built by the team in the old layout |
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-dev-merge.md` | Ported into `clarity.modules.conversation` with a public surface |

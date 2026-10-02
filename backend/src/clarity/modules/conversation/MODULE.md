# conversation - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 |
| Deployable(s) | clarity-api (also mirrored in legacy `src/clarity` for demo) |
| Work package | D1 / chat UX |
| Owner | @clarity |
| Status | built |
| Postgres schema | `conversation` |

## 1. Purpose
Customer chat brain: unified intent taxonomy, context-aware suggestion chips,
template replies, handoff detection, and follow-up chip catalogues. Does **not**
move money; account routes continue into case evaluate / tool layer.

## 2. Public interface (`public.py` facade)
| Method | Input | Output | Errors | Notes |
|---|---|---|---|---|
| `extract_intake` | text | IntakeResult | — | en/si/ta keywords |
| `handle_turn` | text, optional intent | TurnResult | — | route + follow_ups |
| `suggest_for_snapshot` | me/app snapshot | suggestions + more_topics | — | 4–6 chips |

## 3. HTTP endpoints
| Method & path | Permission | Idempotent? | Contract |
|---|---|---|---|
| `POST /v1/conversation/turn` | public/customer | yes | turn |
| `POST /v1/conversation/suggestions` | public/customer | yes | chips |
| `GET /v1/conversation/suggestions` | public | yes | chips |

## 4. Events
None yet.

## 5. Data owned
None (stateless).

## 6. Permissions declared
None yet (deny-by-default still applies on money paths downstream).

## 7. Config keys declared
| Key | Default | Notes |
|---|---|---|
| `conversation.handoff.confidence_floor` | 0.4 | clarify below |
| `conversation.suggestions.limit` | 6 | max primary chips |

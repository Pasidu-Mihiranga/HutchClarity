# conversation - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 |
| Deployable(s) | clarity-api / clarity-worker / clarity-stream |
| Work package | phased |
| Owner | @clarity |
| Status | in-progress |
| Postgres schema | `conversation` |

## 1. Purpose
Intake extract (keyword+structure), language ID (si/ta/en), handoff check, compose reply from templates. LLM via ai-gateway later.

## 2. Public interface (`public.py` facade)
| Method | Input | Output | Errors | Notes |
|---|---|---|---|---|
| `handle_turn` | text, case_id?, facts?, language_hint? | `TurnResult` | - | Full turn |
| `extract_intake` | text | `IntakeResult` | - | Keyword extract |
| `detect_language` | text | `si`/`ta`/`en` | - | Heuristic |
| `check_handoff` | intake | handoff dict | - | - |
| `compose_reply` | intake, facts? | str | - | Templates only |

## 3. HTTP endpoints
| Method | Path | Notes |
|---|---|---|
| POST | `/v1/conversation/turn` | Intake → handoff → reply |

## 4. Events
None yet.

## 5. Data owned
None yet (stateless turn handler).

## 6. Permissions declared
None yet.

## 7. Config keys declared
| Key | Default | Description |
|---|---|---|
| `conversation.handoff.confidence_floor` | `0.4` | Clarify below this score |

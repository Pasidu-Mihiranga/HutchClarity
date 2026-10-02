# timeline - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.timeline`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `builder.py`, `public.py` |

## 1. Purpose
Timeline builder: joins the eight HUTCH evidence sources through integration ports into one hashed evidence snapshot with per-source completeness.

## 2. Public surface (`public.py`)
Other code imports only these names: `TimelineBuilder`, `TimelineRequest`.

## 3. Used by
`clarity.app`, `clarity.modules.case`

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.contracts` | - |
| `clarity.integration.ports` | - |
| `clarity.kernel` | - |

## 5. Data owned
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `timeline` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- Missing or partial sources are flagged, never guessed.

## 7. Migration status (enterprise-plan 21)
Reads through in-process mock drivers (`lite`). R4 adds the `hutch-sim` HTTP drivers behind the same ports.

## 8. Tests
- `tests/unit/test_journeys.py`
- `tests/unit/test_receipts.py`
- `tests/unit/test_timeline_and_adapters.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.timeline` with a public surface (R1) |

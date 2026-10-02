# autopsy - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.autopsy`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` profile); migration notes below |
| Files | `pipeline.py`, `public.py` |

## 1. Purpose
Complaint Autopsy: mask PII first, dedupe, build canonical forms, cluster, map clusters to rules; clusters stay hypotheses until a person reviews them.

## 2. Public surface (`public.py`)
Other code imports only these names: `AutopsyReport`, `CleanComplaint`, `Cluster`, `ClusterStatus`, `Complaint`, `ComplaintAutopsy`, `canonicalise`, `detect_language`.

## 3. Used by
Tests only (no runtime caller yet).

## 4. Depends on
| Package | Through |
|---|---|
| `clarity.ai` | - |
| `clarity.kernel` | - |

## 5. Data owned
In-memory structures in the `lite` profile. Target: one PostgreSQL schema `autopsy` with its own role (ADR-0013), same repository interfaces, same parity suite.

## 6. Invariants
- No complaint text reaches a model unmasked; refused content is not stored.

## 7. Migration status (enterprise-plan 21)
Batch logic in process. Runtime target: serverless batch job (ADR-0028).

## 8. Tests
- `tests/unit/test_autopsy_foresight.py`

## 9. Change history
| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-restructure.md` | Moved into `clarity.modules.autopsy` with a public surface (R1) |

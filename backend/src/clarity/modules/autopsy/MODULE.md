# autopsy - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.autopsy`) |
| Deployable | `clarity-api` today (modular monolith) |
| Owner | TBD |
| Status | built (`lite` and `full`): pipeline from the team's work, event feed, persistence and review workflow AU01 (#13), 2026-10-04 |
| Files | `pipeline.py`, `review.py`, `repository.py`, `service.py`, `public.py` |

## 1. Purpose
Complaint Autopsy: mask PII first, dedupe, build canonical forms, cluster, map clusters to rules; clusters stay hypotheses until a person reviews them.

## 2. Public surface (`public.py`)
Pipeline: `AutopsyReport`, `CleanComplaint`, `Cluster`, `ClusterStatus`, `Complaint`, `ComplaintAutopsy`, `Similarity`, `TrigramSimilarity`, `canonicalise`, `detect_language`.

Service and review (AU01): `AutopsyService`, `ComplaintSource`, `Intake`, `ClusterReviews`, `ClusterReview`, `ReviewedCluster`, `ReviewRefused`, `staff_view`, `HYPOTHESIS_LABEL`, `CONFIRMED_LABEL`, `REJECTED_LABEL`, `AutopsyRepository`, `StoredAutopsyRepository`, `COMPLAINTS`, `CLUSTERS`.

**Removed by AU01:** `ComplaintAutopsy.confirm`. It recorded a verdict by appending `(reviewed by X)` to the cluster's **label**, which put audit data in display text, appended twice if it ran twice, kept no time or note, and had nowhere to persist. `ClusterReviews.record` replaces it.

## 2a. How it runs (AU01)

Event-fed, with the batch as the same code path:

| Step | What |
|---|---|
| `on_complaint_created` | Consumes `complaint.created`. The event carries **no text**, so the service fetches it by id through the `ComplaintSource` seam |
| `accept` | Masks, dedupes by id, and stores the **masked** complaint. A complaint quoting a credential is dropped entirely |
| `rerun` | Redraws clusters over everything kept. Unreviewed clusters are replaced; reviewed ones are never discarded |
| `for_staff` | Every cluster through `staff_view`, which always carries the hypothesis label |
| `review` / supersede | Records a verdict as its own immutable record |

Clustering happens on a re-run and not per complaint, because one complaint is
not a cluster: a cluster is a claim that several complaints share a cause, so
one arriving changes the answer for all of them.

## 3. Used by
`clarity.app.container`, which constructs `AutopsyService` and registers it as
the `autopsy` consumer group for `complaint.created`; and
`clarity.interfaces.http` for `GET /v1/demo/autopsy`, which shows a reviewer
the current clusters.

## 3a. Invariants

- **An unreviewed cluster is labelled as a hypothesis wherever a person sees
  it.** `staff_view` is the only sanctioned representation and always carries
  `hypothesis` and `status_label`. A cluster shown without that label is a
  finding nobody established (I16).
- **A suggested rule id on an unreviewed cluster travels with
  `suggested_rule_is_a_guess`.** A rule id beside a cluster reads as "this is
  caused by that", and nothing has established that yet.
- **Confirmed is not published.** `acted_on` is always false here: turning a
  confirmed cause into a rule goes through the policy lifecycle (plan 20).
- **A verdict is an immutable record**, with a reviewer, a time and a note. The
  cluster's label is display text and is never written to by a review.
- **A second verdict is refused**, not silently applied. Changing one takes
  `supersede`, which keeps both and requires a reason.
- **Only masked complaints are stored** (I13). Masking happens before anything
  else reads a complaint, and the raw text never reaches the repository.
- **The consumer is idempotent** (I7): a complaint is stored under its own id,
  so a redelivery overwrites rather than inflating a cluster's size, which is
  the number a reviewer decides on.
- Time comes from the injected clock (I11).

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

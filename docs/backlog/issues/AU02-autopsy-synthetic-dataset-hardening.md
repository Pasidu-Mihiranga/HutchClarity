# [AU02] Complaint Autopsy: synthetic dataset hardening

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `autopsy` |
| Priority | P0 |
| Depends on | [DATA01](DATA01-synthetic-telecom-dataset-foundation.md), [AU01](AU01-autopsy-event-fed-embeddings-via-the-embed-role.md), [M-GOV](M-GOV-governance-persisted-policy-artefacts-approvals.md) |
| Plan | 02 §3.3 |
| Labels | `wave:w4`, `area:autopsy`, `priority:p0`, `type:feature` |

## Context

Preserve the existing mask-first intake, canonicalisation, deduplication,
similarity seam, clustering, immutable reviews, event consumer, service,
repository, demo route and console summary. This is the missing delta, not a
rebuild.

## Scope

- Replace the main demo's tiny complaint tuple with DATA01 ingestion through
  the existing service and masking path.
- Keep `TrigramSimilarity` for deterministic offline CI. If the current AI role
  seam supports it, add a multilingual embedding provider without coupling to
  a hosted vendor. Disclose the active technique honestly.
- Add manual/scheduled reruns, cluster list, counts, languages, emerging
  synthetic trends, confidence/similarity metadata, masked examples and
  suggested existing rules.
- Mark every unreviewed cluster `HYPOTHESIS`, every unreviewed suggested mapping
  as a guess, and unmatched clusters `NEW / UNMAPPED PATTERN`.
- Preserve immutable confirm/reject records. Superseding requires a reason and
  retains history.
- Create candidate improvements or rules only through the governance boundary.
  Confirmation never publishes or activates a production rule.
- Add an API for UI02; keep business logic out of React.

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | DATA01 | ingested and rerun | meaningful clusters use the existing service | `backend/tests/integration/test_autopsy_dataset.py` |
| 2 | PII-like or credential text | intake runs | it is masked or refused before persistence | `backend/tests/unit/test_autopsy_foresight.py` |
| 3 | duplicate delivery | rerun completes | counts do not inflate | `backend/tests/unit/test_autopsy_foresight.py` |
| 4 | multilingual variants and unrelated noise | clustering runs | related examples cluster for the declared mode and noise is not forced into a known rule | `backend/tests/integration/test_autopsy_dataset.py` |
| 5 | an unreviewed cluster | exposed | hypothesis, guess status, method and synthetic trend provenance are visible | `backend/tests/acceptance/test_autopsy_workspace.py` |
| 6 | an existing review | superseded | a reason is required and history remains immutable | `backend/tests/unit/test_autopsy_foresight.py` |
| 7 | a confirmed cluster | workflow completes | no production rule changes; an unmapped pattern can only create a governed candidate | `backend/tests/integration/test_autopsy_governance.py` |

## Definition of Done

- [ ] Acceptance tests exist and pass; `make check` is green
- [ ] Intentional API changes update OpenAPI, SDK and CHANGELOG.md
- [ ] Autopsy `MODULE.md`, devlog and walkthrough/demo documentation are updated
- [ ] No secrets or real personal data; simulated parts are labelled

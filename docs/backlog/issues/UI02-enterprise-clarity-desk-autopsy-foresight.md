# [UI02] Enterprise Clarity Desk: Autopsy and Foresight workspaces

| Field | Value |
|---|---|
| Wave | W5 Frontend and hardening |
| Area | `frontend` |
| Priority | P1 |
| Depends on | [FE01](FE01-frontend-verified-build-static-ui-retired-next-j.md), [AU02](AU02-autopsy-synthetic-dataset-hardening.md), [F02](F02-foresight-synthetic-scenario-rehearsal.md) |
| Plan | 18 §6; 21 §7 R5 |
| Labels | `wave:w5`, `area:frontend`, `priority:p1`, `type:feature` |

## Context

Replace the console's summary-only treatment with role-appropriate workspaces
that consume backend APIs. Do not implement Autopsy or Foresight logic in React.

## Scope

- Manager/CX Autopsy navigation with clusters, synthetic trend, counts,
  languages, masked examples, hypothesis and suggested-rule status, confidence,
  reviewer and note.
- Review actions for confirm, reject, supersede-with-reason and governed
  candidate creation. No production rule activation.
- Product/operations Foresight navigation with Scenarios, New Rehearsal,
  Results, Synthetic Backtests and Calibration.
- Scenario forms and result views for themes, segments, relative bands,
  mitigations, uncertainty, baseline-vs-swarm and Autopsy comparison.
- Prominent `SYNTHETIC DATA`, `Synthetic scenario`, `Scenarios, not
  certainties` and `Not calibrated on real HUTCH launches` labels as applicable.
- Generated SDK, shared UI/i18n, backend authorization, accessibility and
  responsive behavior.

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | a manager/CX user | Autopsy opens | clusters, trends, masked examples and hypotheses are visible | `frontend/e2e/autopsy.spec.ts` |
| 2 | a reviewer | a review action runs | the API is used and immutable history is displayed | `frontend/e2e/autopsy.spec.ts` |
| 3 | an authorized product/operations user | a rehearsal is configured | the backend runs it and comparison, mitigations and caveats display | `frontend/e2e/foresight.spec.ts` |
| 4 | DATA01 is active | either workspace opens | synthetic provenance is prominent and no value is presented as real HUTCH data | `frontend/e2e/desk-provenance.spec.ts` |
| 5 | an unauthorized user | access is attempted | backend denial and navigation visibility agree | `frontend/e2e/desk-authorization.spec.ts` |
| 6 | keyboard and assistive-technology users | workspaces are exercised | the project accessibility gate passes | `frontend/e2e/accessibility.spec.ts` |

## Definition of Done

- [ ] Acceptance tests, `make check`, `make web-build` and relevant Playwright journeys pass
- [ ] Contract changes update OpenAPI, SDK and CHANGELOG.md
- [ ] Affected `MODULE.md` files, devlog, walkthrough and demo script are updated
- [ ] User-visible strings are available through shared si, ta and en i18n
- [ ] No secrets or real personal data; simulated parts are labelled

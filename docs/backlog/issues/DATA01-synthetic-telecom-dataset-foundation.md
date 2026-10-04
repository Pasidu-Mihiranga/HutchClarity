# [DATA01] Synthetic telecom dataset foundation

| Field | Value |
|---|---|
| Wave | W4 Channels, intelligence and desk |
| Area | `integration` |
| Priority | P0 |
| Depends on | [H01](H01-hutch-sim-as-an-http-service-with-http-drivers.md) |
| Plan | 21 §7 R4 and R6; company synthetic-data decision |
| Labels | `wave:w4`, `area:integration`, `priority:p0`, `type:feature` |

## Context

The company has approved synthetic and anonymous data for the prototype. Real
customer data, MSISDNs, NICs, payment credentials and private complaints remain
prohibited. Extend the existing `hutch-sim` seam rather than replacing it.

Build one coherent world where newly authored complaints correspond to
separate operational facts. Text and ground-truth labels are never operational
evidence.

## Scope

- Deterministic generator with configurable seed, size and date range, exposed
  by `make synthetic-data` or a documented equivalent.
- A canonical fixture of approximately 1,000 to 2,000 complaints without a
  needlessly large committed artefact.
- Fictional archetypes covering students, dual-SIM and family accounts,
  high-data and low-usage prepaid users, small businesses, tourists and
  basic-phone users. These do not represent HUTCH's actual customer mix.
- English, Sinhala, Tamil, Singlish and practical Tamil-English code switching,
  including slang, misspellings, duplicates, repeats, noise, ambiguity,
  incorrect stated causes and partial evidence.
- Coverage of `DUPLICATE_RELOAD`, `RELOAD_NOT_CREDITED`,
  `DUPLICATE_VAS_CHARGE`, corrected VAS consent semantics,
  `VAS_RENEWAL_UNNOTIFIED`, `FUP_CAP_REACHED`, `PACK_EXPIRY_BURN`,
  `PACK_MISMATCH`, `OUTAGE_DURING_PACK`, `LOAN_RECOVERY`,
  `PAYMENT_PENDING_SETTLEMENT`, `PACK_ACTIVATION_FAILED`,
  `FUP_NOT_DISCLOSED`, `SOCIAL_PACK_SCOPE_MISMATCH`, `BALANCE_BURN_PAYG`,
  `NETWORK_SERVICE_DEGRADATION`, `SIM_ESIM_PROVISIONING_FAILURE`,
  `UNEXPECTED_SERVICE_DISCONNECTION` and `UNKNOWN` / `OTHER`.
- Matching compliant and anomalous payment, OCS, catalogue, VAS, consent,
  usage/FUP, CRM, network and SIM provisioning records where supported.
- Complaint schema with synthetic provenance, fictional customer and case ids,
  channel, language, text, time, evaluation-only ground truth, severity, repeat
  count, event references and applicable regulatory references.
- A separate aggregate-only Foresight derivative with no customer id,
  complaint text, conversation or transaction trail.
- `SIMULATED` / `SYNTHETIC` labels on data and analytics.

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | one configuration | generated twice | semantic output is identical | `backend/tests/unit/test_synthetic_dataset.py` |
| 2 | the corpus | provenance and safety are inspected | every record is synthetic and no real identity or secret exists | `backend/tests/unit/test_synthetic_dataset.py` |
| 3 | the corpus | coverage is measured | all 18 families, `UNKNOWN` / `OTHER`, multiple languages, duplicates, noise and missing evidence exist | `backend/tests/unit/test_synthetic_dataset.py` |
| 4 | labelled complaints | evidence references are resolved | separate system facts support ground truth, including compliant and non-compliant VAS cases | `backend/tests/unit/test_synthetic_dataset.py` |
| 5 | text and ground truth | runtime detection runs | neither is accepted as operational evidence | `backend/tests/architecture/test_synthetic_data_boundaries.py` |
| 6 | the corpus | Autopsy ingests it | masked, deduplicated records reach clustering | `backend/tests/integration/test_synthetic_dataset_consumers.py` |
| 7 | the Foresight derivative | its schema is inspected | only aggregates are present | `backend/tests/architecture/test_synthetic_data_boundaries.py` |

## Definition of Done

- [ ] Acceptance tests exist and pass; `make check` is green
- [ ] Affected `MODULE.md` files, devlog and demo documentation are updated
- [ ] New contracts and events follow the repository sync matrix
- [ ] No secrets or real personal data; simulated parts are labelled

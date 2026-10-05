# Module: `offers`

| Field | Value |
|---|---|
| Layer | L4 domain module |
| Status | Built (OFFER01) |
| Owner | security |
| Public surface | `clarity.modules.offers.public` |
| Data | `offers.records` (append-only) |
| Calls | nothing. A leaf |

---

## 1. Purpose

A customer gets an SMS saying HUTCH has given them 10GB free and wants to know
whether to believe it. This module holds what HUTCH actually sent to each number
and compares a pasted message against it.

It is the product's own idea applied to a message instead of a charge: explain
with evidence, say what was checked, and never assert what was not.

## 2. Public surface (`public.py`)

Records: `OfferRecord`, `OFFERS`, `OfferRepository`, `StoredOfferRepository`.

Checking: `check_message`, `compare`, `term_weights`, `Check`, `Comparison`,
`Verdict`, `Signal`, `SignalLexicon`, `MatchThresholds`.

Service: `OfferService`, `OfferPolicy`, `OfferRefused`, and the policy key
names (`CONFIRM_KEY`, `REVIEW_KEY`, `HUTCH_HOSTS_KEY`, and the four
`*_WORDS_KEY`).

## 3. Used by

- `clarity.app.container`, which wires the service and seeds the simulated
  campaigns (`app/offer_seed.py`).
- `clarity.interfaces.http`: `POST /v1/offers/verify` (customer),
  `GET`/`POST /v1/admin/offers` (security admin).

Nothing else. No module calls this one.

## 4. Depends on

`clarity.ai.language` for `query_terms` (one tokeniser for the whole system, so
Sinhala, Tamil and Singlish are segmented the same way everywhere),
`clarity.platform.config.resolver` for every parameter, and
`clarity.platform.persistence` for the collection. No module.

## 5. Data owned

`offers.records`, one row per offer, keyed by `offer_id`.

**No raw MSISDN.** A record carries `subscriber_ref`, the HMAC pseudonym, and
`msisdn_masked` for a staff screen to be legible. A table of "who was sent
what" holding real numbers is a marketing list with a breach radius.

**Append-only.** A customer's check is decided against these records. If one
can be edited after the check, the check proves nothing: somebody could add the
offer the customer asked about and the answer would change retrospectively. A
correction is a new record, and `APPEND_ONLY` backs it with database grants so
the store refuses an UPDATE rather than the code remembering not to issue one.

## 6. Invariants

| # | What |
|---|---|
| O1 | **The verdict is `ON_RECORD`, `NOT_ON_RECORD` or `NEEDS_A_PERSON`, never "scam".** "We have no record of this offer for your number" is something the system knows. "This is a scam" is an inference past it: the record could be missing, the campaign could have come from a partner. The customer is told what was checked and what was found, with the warning signs, and draws the conclusion. |
| O2 | **The pasted text is a hint, never evidence (I2).** It selects which record to compare against. The records decide. A verdict derived from how the message is worded would be derived from the thing an attacker controls. |
| O3 | **Warning signs never move the verdict.** A genuine HUTCH SMS can contain a link and a scam can contain none. Signals are reported as evidence beside the verdict, independently. |
| O4 | **Every parameter is policy (I10).** The two match bars, HUTCH's own domains, and the four signal lexicons all come from `config/policy/offers.yaml`. The bars carry guardrails: a confirm bar near zero would make every message match something, so the system would vouch for a scam. |
| O5 | **A check is bound to its subject (I9).** `OfferService.check` scopes to one `subscriber_ref` before comparing, and `check_message` never sees a number, so it cannot widen the scope. |
| O6 | **Recording an offer is security admin's alone** (`offer:manage`). Whoever holds it decides what the fraud check will vouch for: the same shape of authority as a kill switch, and deliberately held by a role with no money permission. |
| O7 | **Nothing here is a model (I1).** Weighted term containment and an offer code, so a customer can be told exactly why a message did or did not match, and the same input always gives the same answer. |
| O8 | **An expired offer still matches, and says it ended.** Somebody forwarding last month's genuine SMS is not being defrauded, and "HUTCH never sent this" and "HUTCH sent this and it has finished" are different answers. |

## 7. How a message is matched

1. **Scope** to the subscriber's own records.
2. **Weight** each term by how rare it is across those records,
   `log(N / df)` unsmoothed, so a term in every offer weighs zero.
3. **Compare**: the weighted share of the offer's own terms present in the
   message. Containment, not similarity, so a forwarded SMS with a line of chat
   added in front still matches; a symmetric measure would punish extra words.
4. **Or match the code**: an offer code present in the message is a full match
   whatever the wording looks like, because a code is both distinctive and
   usually copied intact.
5. **Band** against the two policy bars: at or above `confirm` is `ON_RECORD`,
   at or above `review` is `NEEDS_A_PERSON`, below is `NOT_ON_RECORD`.

**Why the weighting, recorded because a test found it.** Plain containment
vouched for a message it should not have. A short offer is mostly boilerplate -
"3GB of bonus data has been added to your number, no activation needed" is
fourteen terms of which one is distinctive - so an unrelated campaign written
from the same template shared nine of them and cleared the bar. Weighting took
that case from 0.60 to 0.50, which is `NEEDS_A_PERSON`: still not dismissed,
no longer vouched for.

**Known limit.** With few offers on record the weighting discriminates weakly,
because a term in two of four records still carries weight. The three-verdict
design is what absorbs that: the ambiguous case goes to a person rather than
being guessed either way. **REQUIRES HUTCH VALIDATION** against real campaign
volumes, where discrimination improves.

## 8. Events

None. Nothing reacts to an offer being recorded or a message being checked.

Both are in the audit trail instead (`offer.recorded`, `offer.checked`), which
is where authority exercised and a fraud signal belong. `offer.checked`
records the verdict and the signals and **never the message text**: the text
reaches the hashed payload only, so the same scam checked by four hundred
customers is one correlatable fingerprint in the trail without the trail
becoming a store of what people were sent (I13).

## 9. Tests

- `tests/unit/test_offers.py`: the verdict logic, grouped by the way it can
  fail - vouching for a scam, calling a real offer fake, and guessing on a
  near-match - plus every signal, the lookalike-domain case, and the
  decimal-amount-is-not-a-host case.
- `tests/acceptance/test_offers_api.py`: the permission split against every
  staff role and a customer, the subject binding, and the record-then-match
  loop.

## 10. Change history

| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-05 | `docs/devlog/2026/2026-10-05-OFFER01-offer-verification.md` | The module, the two permissions, the policy file, the three routes, the console tab and the customer screen |

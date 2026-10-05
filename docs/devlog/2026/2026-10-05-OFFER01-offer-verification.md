# 2026-10-05 - OFFER01 - "Is this Hutch offer real?"

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga |
| Work package | OFFER01 (new, requested feature) |
| PR / commit | feat/offer-verification |
| Units touched | `clarity.modules.offers` (new), `clarity.app`, `clarity.interfaces.http`, `clarity.platform.{security,audit,persistence}`, `config/policy`, console, customer-web |

Written by an AI coding agent (Claude Code) under AGENTS.md §12.

## What changed

A customer gets an SMS saying HUTCH has given them 10GB free. They paste it into
the app and are told whether an offer on record for **their** number matches it.
A security admin records what HUTCH actually sent, from a new console tab.

**New module `clarity.modules.offers`** (a leaf; calls nothing). Records, a
deterministic comparison, and a service. Full design in its
[MODULE.md](../../../backend/src/clarity/modules/offers/MODULE.md).

**Two permissions**, because they are two jobs with very different authority:

- `offer:verify` - a customer checks their own messages. `Role.CUSTOMER`.
- `offer:manage` - record what HUTCH sent. `Role.SECURITY_ADMIN` **alone**.
  Whoever holds this decides what the fraud check will vouch for, so it is the
  same shape of authority as a kill switch, and it sits with a role that holds
  no money permission.

**Three routes**: `POST /v1/offers/verify` (subject-bound), `GET` and
`POST /v1/admin/offers`.

**Policy**: `config/policy/offers.yaml` - the two match bars (with guardrails),
HUTCH's own domains, and four signal lexicons including Sinhala and Tamil,
because a smishing SMS is written in the language of its target.

**Seed**: a new synthetic subscriber `+94785720767` (Sanduni, an ordinary
account with nothing wrong on it) and four simulated campaigns against it, one
deliberately expired. All labelled `hutch-sim` (I16).

**UI**: a console tab at `/offers` for the security admin (gated on
`offer:manage`, using the E1 design system and the E2 accessibility patterns),
and a customer screen at `/check-message` reached from Home.

**Audit**: `offer.recorded` and `offer.checked`.

## The decision that shaped everything: the verdict is not a scam flag

Three answers come back - `ON_RECORD`, `NOT_ON_RECORD`, `NEEDS_A_PERSON` - and
none of them is "this is a scam". There is a test asserting the word never
appears in the payload.

"We have no record of this offer for your number" is something the system
knows. "This is a scam" is an inference past it: the record could be missing,
the campaign could have come from a partner, and here the corpus is simulated.
The customer is told what was checked, what was found, and what in the message
is worth looking at, and draws the conclusion themselves. That is the same rule
the rest of Clarity follows, and the thing that actually protects somebody is
not a verdict but knowing HUTCH has no record of it *and* that it is asking for
their PIN.

The third verdict exists for the case the other two would both get wrong: a
real offer forwarded with half of it cut off, and a scam built by editing a real
one, look the same from the outside. Guessing between those is what a person is
for (I2).

## Other decisions

- **Warning signs never move the verdict.** A genuine HUTCH SMS can contain a
  link and a scam can contain none, so signals are reported independently as
  evidence. There is a test for a real offer with a link in it still reporting
  the link.
- **The pasted text is a hint, never evidence (I2).** It selects which record
  to compare against; the records decide. A verdict influenced by the wording
  would be influenced by the one thing an attacker controls, and there is a
  test that pure scam wording with no offer content cannot produce a match.
- **No MSISDN in the offers table.** A record carries the HMAC pseudonym and a
  masked number for a staff screen. A table of "who was sent what" holding real
  numbers is a marketing list with a breach radius.
- **The collection is append-only.** A customer's check is decided against
  these records; if one can be edited afterwards the check proves nothing,
  because somebody could add the offer that was asked about and change the
  answer retrospectively. A correction is a new row, and `APPEND_ONLY` backs it
  with database grants.
- **`offer.checked` never records the message text.** It records the verdict
  and the signal codes; the text reaches the hashed payload only. So the same
  scam checked by four hundred customers is one correlatable fingerprint in the
  trail without the trail becoming a store of what people were sent (I13).
- **Nothing is a model.** Weighted term containment and an offer code, so a
  customer can be told exactly why a message did or did not match and the same
  input always gives the same answer (I1, I11).
- **The customer opens the screen; the chat does not guess.** The first design
  watched what somebody typed and offered a check when it looked like a
  forwarded offer. That is the client inferring intent - the pattern FE01
  called out as an I1 violation elsewhere in this app - and it fails in the
  direction that matters: a scam the heuristic missed gets no check at all.

## A false positive the tests found, and the fix

Plain term containment vouched for a message it should not have. The acceptance
test wrote a "weekend bonus" campaign and asserted it did *not* match before
being recorded; it matched at exactly 0.60, the confirm bar.

The cause is that a short offer is mostly boilerplate. "Happy Avurudu from
Hutch. 3GB of bonus data has been added to your number, valid for 7 days. No
activation needed." is about fourteen terms, of which one ("avurudu") is
distinctive. An unrelated campaign written from the same template shared nine
of them.

The fix is the standard one: weight each term by how rare it is across the
offers on record, `log(N / df)` unsmoothed, so a term appearing in *every*
offer weighs exactly zero. That took the case from 0.60 to 0.50, which is
`NEEDS_A_PERSON`: no longer vouched for, not dismissed either. Where no term is
distinctive (one offer on record, or several written identically) the weights
are all zero and it falls back to unweighted containment, because "nothing here
is distinctive" is not a reason to match nothing.

**Known limit, recorded rather than tuned away.** With few offers on record the
weighting discriminates weakly: a term in two of four records still carries
weight. The three-verdict design is what absorbs that. **REQUIRES HUTCH
VALIDATION** against real campaign volumes.

## What three architecture tests caught

Worth recording because all three were right and none was worked around:

1. `test_no_owner_entry_is_dead` - `OWNERS` had an `offers` prefix that no
   collection in `app/collections.py` used. Registered it.
2. `test_every_module_has_a_public_surface_and_a_module_doc` - no `MODULE.md`.
   Written.
3. `test_every_route_is_classified_exactly_once` - three unclassified routes.
   Added to `SIGNED_IN` in the route contract.

## Docs updated

- [x] This devlog
- [x] `backend/src/clarity/modules/offers/MODULE.md` (new)
- [x] `docs/modules.md` (new module row)
- [x] `CHANGELOG.md` (three new routes, two new permissions, SDK methods)
- [x] `contracts/openapi.json` and the acceptance golden, regenerated
- [x] `frontend/packages/sdk` regenerated and the client extended
- [ ] `ARCHITECTURE.md`: needs the module in its status table. Not done in this
      change; flagged below.
- [ ] ADR: the "verdict is not a scam flag" decision is a product decision with
      a security argument behind it and arguably deserves one. Not written;
      flagged below.
- [ ] Walkthrough: a WT for the journey (paste a message, see the verdict;
      record an offer, see it take effect) is not written.

## Tests

- `tests/unit/test_offers.py`: 24. Grouped by the way the feature can fail -
  vouching for a scam, calling a real offer fake, guessing on a near-match -
  plus every signal, the lookalike-domain case (`nothutch.lk` must not pass as
  `hutch.lk`) and the decimal-amount-is-not-a-host case.
- `tests/acceptance/test_offers_api.py`: 18. The permission split against six
  staff roles and a customer, the subject binding (the same message, two
  numbers, two answers), and the record-then-match loop.
- `tests/architecture`: 133 pass.
- `tests/acceptance/test_route_contract.py`: passes.
- `ruff check` clean; `mypy --strict` clean on the new module and the seed.
- Frontend `npm run typecheck`: clean in all five workspaces.
- **Not run**: the full `make check`, `make e2e`, and no browser test covers
  either new screen.

## Open issues / next step

1. **`ARCHITECTURE.md`** needs the module added to its status table.
2. **A walkthrough and an e2e spec** for both screens.
3. **An ADR** for the verdict vocabulary.
4. **Real campaign records**: the seed is simulated. Production reads the CVM
   or campaign management system through an integration port, per subscriber,
   with its own effective window. **REQUIRES HUTCH CONFIRMATION.**
5. **Reporting**: `offer.checked` makes "four hundred people asked about the
   same message this hour" answerable, which is a genuine early-warning signal
   the assurance module could consume. Not built.

# 2026-10-03 - C04 - Intake, and what the Singlish number was really saying

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | C04 (`docs/backlog/issues/C04-intake-keyword-rules-first-extract-role-when-uns.md`, #23), Wave 3 |
| PR / commit | not committed at time of writing |
| Units touched | `ai.language` (moved from `modules.knowledge.terms`), `modules.conversation` (`intake.py`, `service.py`, `orchestrator.py`, `public.py`), `app.container` |

## What changed

- **`conversation/intake.py`**: the rule table, ordered rather than scored, with
  Sinhala, Tamil and Singlish alternations on every rule; Singlish language
  detection; and the `extract` role seam.
- **`ai/language.py`**: the Singlish lexicon and tokenisation, moved out of the
  knowledge module so intake and retrieval share one copy.
- **`intake_heldout.jsonl`**: a held-out set, written before the rules were
  touched.
- `IntakeResult.assisted` records whether a model was consulted.

## The measurement this started from

```
en     F1=0.688   5 errors / 20
si     F1=0.559   7 errors / 20
ta     F1=0.520   8 errors / 20
si-en  F1=0.305  13 errors / 20
```

**Thirteen of the twenty Singlish examples classified as FALLBACK.** Not
misclassified: unclassified. The rule table held no Singlish vocabulary at all,
so a customer writing "Mage wegaya adu karala ai?" reached no rule and got the
generic prompt. After C04:

| language | before | tuned set | held-out set |
|---|---|---|---|
| en | 0.688 | 1.000 | 1.000 |
| si | 0.559 | 1.000 | 1.000 |
| ta | 0.520 | 0.930 | 1.000 |
| si-en | **0.305** | **0.930** | **1.000** |

Language detection: 116 of 116 across both sets.

## The held-out set, and why it exists

A keyword rule can always be made to pass the sentence it was written for, so a
good number on the set the rules were extended against says very little. I
wrote `intake_heldout.jsonl` **first**, 36 examples across the four languages,
and did not look at it while extending the rules. It is the only number here
that says anything about a sentence nobody has seen.

It also caught me out: three of my held-out examples turned out to be verbatim
duplicates of lines in the tuned set, which made that part of it not held out at
all. `test_the_held_out_set_is_independent_of_the_tuned_one` found it, and the
three were rewritten. Held-out F1 stayed at 1.000 afterwards.

**Neither set validates a keyword set.** The `intake` gate requires 300
examples per language and these hold 20 and 9, so the gate still reports
UNEVALUABLE at F1 1.000:

```
UNEVALUABLE  intake.intent_f1 [si]:    1.000 (gate 0.900, n=20) below the 300 this gate requires
UNEVALUABLE  intake.intent_f1 [si-en]: 0.930 (gate 0.900, n=20) below the 300 this gate requires
```

That is the right answer and I have not touched the minimum to make it green.
Twenty examples per language cannot tell a rule that works from a rule that
happens to match twenty sentences, and the gate saying so is more useful than a
pass.

## Decisions made

1. **Rules are ordered, not scored against each other.** The previous table was
   a flat list of (pattern, intent, confidence) and took the highest confidence
   matching anywhere, which made specificity a function of whatever number
   somebody typed: "why was LKR 49 deducted from my balance" matched the
   unexpected-charge rule at 0.88 and the balance rule at 0.85, so it
   classified as an unexpected charge because of a 0.03 difference nobody
   intended. First match wins now, so a rule is more specific than another
   because it is above it, which is reviewable in a diff.

2. **The Singlish lexicon moved to `clarity.ai.language`.** Two modules need
   the same vocabulary for different jobs: knowledge expands a query into the
   English its corpus uses (K02), conversation classifies an intent. A lexicon
   in one would be duplicated by the other and the duplicate would drift. The
   layer is already right: `clarity.ai` is "language only, never authority",
   and every function in it is deterministic. The K02 devlog predicted this
   move.

3. **Two markers make a sentence Singlish, not one.** "Please reload my
   account" is English and carries "reload", which is in the shared lexicon.
   Reading it as Singlish would answer an English speaker in Sinhala.

4. **Singlish is answered in Sinhala.** The approved templates exist in si, ta
   and en (I15) and should not grow a fourth: a Singlish speaker writes Latin
   script and reads Sinhala. Answering in English would be a guess about
   literacy. `reply_language` is where that is decided, because
   `compose_reply` was otherwise falling through to English.

5. **A model cannot overrule a confident rule.** The `extract` role is asked
   only below 0.70, and what it returns is capped at `LIKELY` and validated
   against the catalogue. A model that can overrule a matched phrase can
   reroute a customer on a whim, and the router uses the confidence to decide
   whether to pull someone out of a flow they are already in (C02).

6. **An invented intent is rejected, not accepted.** A model naming
   `REFUND_EVERYTHING_NOW` gets a FALLBACK, because accepting it would let a
   model reach a flow no rule can reach, which is agency this layer does not
   have (I1).

7. **`assisted` is recorded on the result.** A reader of the audit needs to
   know an intent came from a model rather than a matched phrase, the same way
   `guard_assisted` already says so for the guard.

## Four bugs, and three were about writing systems

**1. `ජාල` is a substring of `අන්තර්ජාලය`.** "network" sits inside "internet",
so "අන්තර්ජාලය ඉතා මන්දගාමී වේ" ("the internet is very slow") classified as a
network outage. Sinhala has no spaces where English has them and `\b` cannot
help, so the rule now uses a negative lookbehind. This is the kind of bug that
only shows up if the dataset has real sentences in the language.

**2. `සක්‍රිය` and `සක්රිය` are the same word and two different strings.**
Sinhala writes conjunct consonants with a zero-width joiner, which a reader
cannot see and `re` cannot ignore, so a Sinhala activation request missed the
activation rule. Text is now NFC-normalised with zero-width characters stripped
before matching, so patterns can be written plainly.

**3. Tamil and Sinhala inflect, and my patterns were nominative.** "வழக்கு"
(case) appears as "வழக்கின்", "கணக்கு" (account) as "கணக்கிலிருந்து". Patterns
match stems now. There is no stemmer for either language here and there should
not be a guessed one: shortening the pattern is honest, a hand-rolled stemmer
would not be.

**4. `සේවාව` means "service" and I had it meaning "subscription".** It appears
in unexpected-charge complaints ("I was charged for a service I do not know"),
so the VAS rule was capturing them. Removed; "දායක" (subscription) stays.

Also: "ganna" means "to take" or "to buy", not "to activate", so "Data package
ganna but wada karanne naththa" was reading as an activation request rather than
a pack that does not work.

## Contract and plan notes

- **No `/v1` contract change**; snapshot unchanged.
- **`clarity.ai.language` is a new module in an existing layer**, not a new
  module in the module registry, so `docs/modules.md` is unchanged and no
  dependency edge was added. `knowledge` and `conversation` both import it
  downward (L4 to L3), which the layer rule allows; `"conversation": set()` and
  `"knowledge": set()` both still hold.
- **`detect_language` returns `si-en`**, which is a fifth value callers may
  see. Everything in the repository that switches on it goes through
  `reply_language`, and `test_intake_set.py` had a test asserting the old
  behaviour whose docstring said failing would be the point. It now asserts the
  new behaviour.
- The rule table is code, not content. It should be versioned policy content
  under plan 20 like the flows are, which is the same gap C02 recorded.

## Docs updated

- This devlog, `backend/src/clarity/modules/conversation/MODULE.md`,
  `CHANGELOG.md`, `ARCHITECTURE.md`, `plan.md` (#23 ticked), and the knowledge
  `MODULE.md` where it referenced `terms.py`.
- No new event, no `.env.example` change.

## Tests run

- `make check`: **1679 passed, 544 skipped** (1656 before C04).
- `make contracts-check`: unchanged.
- `make eval`: `intake.intent_f1` now clears 0.90 in all four languages and
  stays UNEVALUABLE for sample size (above).
- Acceptance 1 (`tests/evaluation/test_intake.py`, 23 tests): F1 per language
  on the tuned set and on the held-out set, both gated at 0.90.
- Plus properties of the table itself: every intent is reachable by some rule
  (an unreachable intent is a dead journey), no two rules share a pattern, and
  **every rule carries a Sinhala or Tamil alternation** unless its words are
  loanwords written the same way in all four, which is the check that would
  have caught the original Singlish gap.
- Non-vacuity: removing the shared lexicon from the Singlish markers fails
  `test_every_singlish_example_is_detected_as_singlish`. The before-measurement
  above is the evidence acceptance 1 failed before the change.

## Known gaps

- **The gate stays UNEVALUABLE** until there are 300 examples per language
  (above). That is 1200 labelled utterances and it is content work, not code.
- **No cassette, so the `extract` seam has never run against a model.** Tested
  with stubs for the four cases that matter: not asked when confident, asked
  when unsure, an invented intent rejected, a failure leaving the rules'
  answer. Same blocker as K02 and K03.
- **The romanisations are an ASSUMPTION.** Sinhala has no standard
  romanisation, so "gaasthu", "gasthu" and "gastu" are one word and each
  spelling has to be listed. **REQUIRES HUTCH CONFIRMATION** against real
  message traffic, which is also the only thing that can tell us which
  spellings customers actually use.
- **Slot extraction is unchanged** and its gate reports `n=2`. The amount regex
  is the same one C01 shipped; C04's scope was the intent.
- The two remaining tuned-set misses are both an intent pair a human would
  argue about: a charge for an unrecognised service read as a subscription
  question, and a case-status question in Tamil read as a refund question.

## Next step

C05 (#24), the last of Wave 3: the customer chat experience on flows, with
confirm cards, the citations K03 produces, and handoff.

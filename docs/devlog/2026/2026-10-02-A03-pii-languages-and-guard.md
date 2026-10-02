# 2026-10-02 - A03 - PII masking in four languages, and the guard role

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | A03 (issue #4), Wave 2; I13, I1, plan section 10.3 |
| Units touched | `clarity.ai` (`pii.py`, `guard.py`), `tests/unit/test_pii_languages.py`, `tests/evaluation/` |

## The gap this found

`PiiKind.NAME` existed in the enum **with no detector behind it**. Numbers and
NICs masked correctly in all four languages; the customer's name went to the
model untouched in every one of them. Nothing in the suite noticed, because
masking was only ever tested on English examples and none of them asserted on a
name.

So I13 was being broken on the one field most likely to identify someone by
name, in a system whose whole masking story is "no real customer data reaches
any LLM".

## What changed

- `pii.py` gained name detection: per-language introduction phrases, honorifics, a short Sri Lankan surname gazetteer, and the Sinhala and Tamil renderings of those surnames.
- `guard.py` (new): injection detection. Heuristics always, locally; the `guard` role as an assist that can only ever **add** a refusal.

## Decisions made

- **High-precision signals, not capitalisation.** Full name recognition needs a model, and masking cannot depend on one: masking happens *before* anything is sent anywhere (I13), so it cannot itself call a provider. Each pattern is a case where the text says "this is a name" rather than a guess.

- **"I am" is deliberately not an introduction.** The first version treated it as one and masked "I am **not happy**" as a name. It is far more often an ordinary sentence, and a reply built from text with the nouns removed is not an explanation anyone can read. Over-masking is its own harm, so the golden set checks both directions: eight PII cases where nothing may survive, and eight ordinary complaints where nothing may change.

- **The guard looks for text addressing the system, not for the word "refund".** "Please refund it" is what most of these customers are actually saying. A guard that holds it stops people getting help, so six genuine complaints, including two in Sinhala and Singlish, are pinned as must-pass.

- **The guard role can add a refusal but never clear one.** A model that has been talked into saying "this is fine" must not be able to unlock anything. A broken guard provider returns the heuristic verdict rather than blocking the customer, because the guard is a second line: what actually prevents an action is that amounts come from the decision record, execution needs a confirmation token minted outside the AI path, and the tool layer refuses anything outside `Decision.allowed_actions` (I1).

- **The safety set asserts on the world, not on the reply.** A model persuaded to *say* it refunded you is harmless; a system that refunds is not. So the test sends all ten injections through `evaluate` and then checks the balance and the receipt count.

## A bug worth recording

The Tamil introduction pattern silently matched nothing, so every Tamil name
leaked while the test for it looked like it was passing on the others. The cause
was a **one-character encoding corruption**: the Tamil pulli (U+0BCD) in the
pattern had become the Sinhala al-lakuna (U+0DCA). The two are indistinguishable
by eye, and no reviewer would have caught it in a diff.

The local-script patterns are now written as explicit `\uXXXX` codepoints with
the transliteration in a comment, so the file states which character it means
rather than relying on the reader's font. This is the kind of thing a
per-language golden set exists to catch, and it caught it on the first run.

## Tests

- `tests/unit/test_pii_languages.py` (new, 33 tests): acceptance 1. Eight PII sets across English, Sinhala, Tamil and Singlish, each asserting no raw identifier survives, that a token replaces it rather than deleting it, and that the reply restores. Eight ordinary complaints asserting masking changes nothing. A name is asserted found in every language.
- `tests/evaluation/test_safety_set.py` (new, 25 tests): acceptance 2. Ten injections across four kinds, asserting zero money moved and no receipt issued, each held for the right reason, refusals carrying stable upper-case codes and the matched phrase for the audit record, six genuine complaints passing, and the guard-role assist behaving in all four states (adds, cannot clear, broken, absent).
- `make check`: **1309 passed, 512 skipped**.

Both acceptance tests verified non-vacuous: removing name detection fails the
language suite; making the guard allow everything fails the safety suite.

## Open issues / next step

- The surname gazetteer is short and deliberately so. It is not meant to be exhaustive, and the introduction patterns carry most of the weight. A name with no introduction phrase and an unlisted surname still reaches the model, which is a real limitation rather than a solved problem: closing it properly needs the `guard` or `extract` role, or Presidio with Sri Lankan recognisers as plan 19 section 2.1 specifies.
- The guard is not wired into any request path yet; nothing calls `Guard.check`. It belongs in the conversation intake (C04) and at the gateway boundary, and the gateway wiring is the same `container.py` change A01 is waiting on.
- `tests/evaluation/` is a new directory. A05 will add the scored golden sets alongside this safety set.

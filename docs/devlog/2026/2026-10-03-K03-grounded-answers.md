# 2026-10-03 - K03 - Grounded answers, and a gate that now fails honestly

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | K03 (`docs/backlog/issues/K03-grounded-answers-compose-with-citations-citatio.md`, #33), Wave 3 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.knowledge` (`citations.py`, `answers.py`, `cache.py`, `service.py`), `modules.conversation` (`router.py`, `orchestrator.py`), `app` (`container`, `flow_tools`, `knowledge_seed`), `interfaces.http`, `contracts.events`, `scripts/evaluate.py`, `config/ai/gates.yaml` |

## What changed

- **`citations.py`**: the citation verifier. Every citation in an answer is
  checked against the retrieval behind it: retrieved, effective,
  audience-allowed, well formed.
- **`answers.py`**: `compose_answer`. Template path (the source's own words,
  cited), optional model path (verified, template on failure), refusal when
  there is no source.
- **`cache.py`**: generic answers keyed by corpus fingerprint, language and
  audience.
- **`service.py`**: `KnowledgeService.ask`, one call that retrieves, composes,
  verifies and caches.
- **`knowledge.published@v1`**, produced through the outbox and consumed by the
  `knowledge-cache` group.
- **`/v1/knowledge/search` is served by the module**, and the simulated help
  articles are published into the registry so it has something to serve.
- **`KNOWLEDGE_QA` reaches `answered`**, with a deterministic retrieval in the
  router.

## The headline, and it is a failure

`rag.citation_accuracy` went from `UNEVALUABLE` to:

```
FAIL  rag.citation_accuracy: 0.931 (gate 0.980, n=29) below the gate
```

Two of 29 answered golden-set queries cite a source that is **real, retrieved,
effective and audience-allowed, and is the wrong document**. The citation
verifier cannot catch it, because there is nothing wrong with the citation: the
answer is grounded in a genuinely published clause that happens to be about
something else.

**I left it failing.** The cause is that lexical retrieval cannot tell a
relevant hit from an irrelevant one on this corpus, which is the embedding model
the system does not have (K02 devlog). Lowering the gate to 0.93 would convert
a measured problem into a satisfied number, and the gate layer A05 built exists
precisely to stop that. AGENTS.md says to fix the cause and never weaken the
test; the cause is outside this module and now has a number attached to it.

What is measured is deliberately **not** "did the citations verify". The
template path makes every citation verify by construction, so that number would
be 1.00 on the day it was written, and it would be the vacuous measurement the
`UNEVALUABLE` status was invented to refuse. What is measured is whether the
answer cited a source the golden set says would ground it.

## Decisions made

1. **The template path quotes the source verbatim and does not paraphrase.**
   I15 allows no free text to customers from a model, and a paraphrase of a
   policy clause is a new claim about policy made by whoever wrote the
   paraphraser. Quoting the clause and citing it is the strongest grounded
   answer available without a model, and it is the fallback the model path
   lands on, so the floor is never worse than "here is what the rule says, here
   is where to check it".

2. **A model answer that fails verification is discarded whole, not repaired.**
   There is no "drop the bad citation and send the rest": a sentence whose
   support was removed is a sentence with no support, and the model's other
   sentences were written in the context of the claim it could no longer make.

3. **A failed model answer falls back to the template, not to a refusal.** The
   sources were real and the template quotes them, so a correct answer is
   available and refusing would withhold it. The model's fault codes travel
   with the answer, so the audit records what it did.

4. **A composer is not even asked when nothing was retrieved.** A model given
   no context answers from its training, which is a guess with a confident
   voice. The refusal is decided before the model is reached.

5. **Staleness is impossible rather than prevented.** The corpus fingerprint is
   part of the cache key, so publishing anything makes every earlier entry
   unreachable. The `knowledge.published` event still fires and the consumer
   still drops dead entries, but correctness does not depend on a message
   arriving: an invalidation scheme that does is one lost message away from
   quoting last month's terms with this month's confidence.

6. **The fingerprint includes each version's window**, not just the set of
   refs. Closing a version changes what is in force without adding one, and a
   key over refs alone would not notice.

7. **The audience is in the cache key**, because the retrieval filter went to
   some trouble to keep staff sources out of a customer's result set and a key
   without it would hand one over anyway.

8. **The seed lives in `app/`, not in the module.** A module that ships its own
   content is a module whose content nobody reviews. And nothing is invented:
   the five articles already exist in the repository and are already served by
   this route, so publishing them labelled `hutch-sim` moves content rather
   than authoring it (I16). **REQUIRES HUTCH CONFIRMATION** for the real
   corpus.

9. **`/v1/knowledge/search` stays additive.** `articles` keeps its shape and
   place because `/v1/clarity/route` and `/v1/conversation/turn` both read it
   and the SDK is generated from the schema. The snapshot was regenerated and
   the only change is the description, since the handler returns an untyped
   object.

10. **The route takes no audience parameter.** Accepting one from the query
    string would let anyone ask for staff sources (I9).

## Four bugs the tests found, three of them mine

**1. A terminal flow state trapped the conversation.** A customer who asked one
knowledge question could never ask a second: the flow sat in `answered` or
`offer_person`, which have no transitions, so `_entry_state` resumed there and
no state ran. C02 handled the cross-flow case ("a flow already in a terminal
state does not trap anyone") and missed the case where the same flow claims the
new intent. A finished flow now restarts: a finished journey plus a new message
is a new journey. Found by an acceptance test that asked three questions in one
case.

**2. An answer could read as verified without having been verified.**
`GroundedAnswer.grounded` was `kind is not REFUSAL and report.ok`, and an empty
`CitationReport` means "nothing was checked" while `all([])` is true. So an
answer carrying citations with a default report was grounded, and the cache
stores anything grounded. `grounded` now requires every claimed citation to
appear in the report's verified set. Found by a cache test, not a verifier test:
the verifier never produces an empty report, so only a caller constructing one
could reach it.

**3. A state's own output was invisible to its own transitions.** `answer_found`
reads `citations`, and a retrieval that produced them this turn put them in
`produced` while the conditions were evaluated against `facts`. So the flow
retrieved, found sources, and still took its `no_source` exit. C02 threaded
`proposal_id` separately for exactly this reason; it is now generalised so the
next produced fact needs no new argument.

**4. The deterministic retrieval was missing entirely.** `KNOWLEDGE_QA.retrieve`
is marked `agentic`, and C03's agent only runs with a planner, so with no model
configured nothing called `search_knowledge` and the flow always offered a
person for questions the corpus answers. ADR-0009 requires every step to work
without a model, and this step did not. The router now retrieves with the
customer's own words in any state that allows the tool.

## The precision work I tried and reverted

Writing the acceptance test for "no source" exposed a false positive: "what is
the share price of the company?" returned a cited answer from the
pack-activation article, because "price" appears in it. One incidental word out
of three, presented as grounded.

`min_relative_score` cannot catch that, and the reason is worth recording: it is
a share of the **best** hit's score, so a single weak hit is always 1.0 of
itself. I tried two guards and measured both against the golden set:

| Guard | recall@5 | Singlish | Tamil |
|---|---|---|---|
| none | 0.967 | 1.000 | 1.000 |
| coverage, a third of the query's words | 0.900 | 0.800 | 1.000 |
| coverage, two words | 0.733 | 0.600 | **0.000** |

Then I looked at why, instead of tuning further:

```
correct hits  n=51  min score=0.438  median=1.100
wrong hits    n=58  min score=0.310  median=0.684  max=1.160
correct hits matching only 1 term: 25 of 51
wrong   hits matching only 1 term: 45 of 58
```

**Half the correct hits match exactly one term**, and the score distributions
overlap completely. No coverage rule and no absolute floor separates them,
because what separates them is meaning. Both guards were reverted and the
reasoning is in a comment at the cut in `retrieval.py`, so the next person to
have the idea finds the measurement rather than repeating it.

A smaller finding on the way: the coverage rule measured against the *expanded*
query terms, which the Singlish lexicon inflates, so a document matching both
words that mattered covered two of ten. Coverage has to be counted per word the
customer wrote. That shaped the measurement above and is why the first row of
the table is not worse.

## Contract and plan notes

- **OpenAPI snapshot regenerated**, description only. `make contracts-check`
  passes.
- **New event**: `knowledge.published@v1`, in `contracts.events`, in plan 21
  section 11.3, with a round-trip sample in `tests/support/events.py`.
- **No new module edge.** `"knowledge": set()` still holds. The conversation
  module reaches the knowledge module through the `ToolCaller` protocol the
  composition root supplies, exactly as C02 arranged for the case tools, so
  `"conversation": set()` holds too.
- **The semantic cache is exact, not semantic.** Plan 22 section 7 says "exact
  and meaning cache". The key is a hash of normalised, folded, Singlish-expanded
  terms, which catches punctuation, case, word order and the common Singlish
  spellings, and is not a meaning cache. A meaning cache needs embeddings. Named
  `AnswerCache` rather than `SemanticCache` so the name does not overclaim.

## Docs updated

- This devlog, `MODULE.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, `docs/modules.md`,
  `plan.md` (#33 ticked), plan 21 section 11.3, `config/ai/gates.yaml`.
- No `.env.example` change.

## Tests run

- `make check`: **1639 passed, 544 skipped** (1608 before K03).
- `make contracts-check`: passes after regeneration.
- `make eval`: `rag.recall_at_5` PASS at 0.967; `rag.citation_accuracy`
  **FAIL at 0.931**, deliberately (above).
- Acceptance 1 (`test_citation_verifier.py`, 25 tests): an answer citing a
  chunk that was not retrieved is blocked, and the composed answer never
  carries the hallucinated citation or the claim it supported. Plus the right
  source at the wrong version, a staff source cited to a customer, a lapsed
  version, uncited claims, and malformed attempts.
- Acceptance 2 (`test_assistant.py`, black box over `/v1`): a question with no
  source says so and routes to a person, with `reason=no_published_source`.
  Plus the other half, so the module cannot pass by refusing everything, and
  the invariant across both: either the reply is grounded and cites a version a
  reader can look up, or it is a refusal and cites nothing.
- `test_knowledge_cache.py`, 16 tests: staleness, the key's components, and
  each of the four things `put` refuses.
- Non-vacuity, two probes:
  - removing the "was it retrieved" check fails the two acceptance-1 tests and
    the wrong-version one.
  - removing the explicit no-source refusal fails only
    `test_a_composer_is_not_even_asked_when_there_is_no_source`, which turned
    out to be informative: the refusal has two independent causes, because a
    template built from an empty trace carries no citations and is refused by
    the uncited rule instead. The probe showed the second layer holding.

## Known gaps

- **`rag.citation_accuracy` fails at 0.931** and needs the embedding model
  (above). This is now the clearest statement of the cost of that gap: a
  measured gate failure rather than an argument.
- **No cassette, so no model path is exercised against a real model.** The
  composer seam is tested with stubs, honestly and adversarially, but
  `AnswerKind.MODEL` has never been produced by a model. Same blocker as K02.
- **The cache is exact, not semantic** (above).
- **The refusal wording in Sinhala and Tamil is unreviewed.** **ASSUMPTION**,
  written for the prototype. Plan 22 section 10's `language_review` gate is what
  would clear it and it reports UNEVALUABLE until native-speaker ratings exist
  (FE01, #28). **REQUIRES HUTCH CONFIRMATION** before it reaches a customer.
- **Knowledge sources still do not go through `PolicyGovernance`**, so there is
  no maker-checker gate on new legal text. Unchanged from K01 and still the
  module's largest governance gap.
- The quoted template answer can begin mid-list, because the best-matching
  chunk of a help article is often its steps. It reads acceptably and is not
  wrong, but a composer that knew about structure would do better.

## Next step

Wave 3's remaining items are C04 (#23), intake with the `extract` role and
Singlish support, and C05 (#24), the customer chat experience on flows with
confirm cards, citations and handoff. C05 is where the citations this change
produces become something a customer can see and click.

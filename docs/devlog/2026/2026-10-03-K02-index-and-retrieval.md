# 2026-10-03 - K02 - Retrieval, and what measuring it found

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | K02 (`docs/backlog/issues/K02-index-and-retrieval-bm25-lite-pgvector-hybrid-f.md`, #32), Wave 3 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.knowledge` (`terms.py`, `bm25.py`, `config.py`, `retrieval.py`), `ai.evaluation`, `app.container`, `app.settings`, `scripts/evaluate.py`, `config/ai/{retrieval,gates}.yaml` |

## What changed

- **`terms.py`**: one tokeniser for the index and the query, English suffix
  folding, and a Singlish lexicon that expands a query into the English the
  corpus is written in.
- **`bm25.py`**: Okapi BM25, built once and scored against the candidate set.
- **`config.py`** and **`config/ai/retrieval.yaml`**: top-k, BM25 constants,
  fusion weights and rerank bonuses out of code (I10).
- **`retrieval.py`**: `KnowledgeRetriever` (filter, rank, rerank, cut),
  `RetrievalTrace`, the `SemanticRanker` seam, and `RewritingRetriever` for the
  optional `extract`-role query rewrite.
- **The `rag` release gate is now evaluable**: a golden set, a `load_rag`
  loader, a `recall_at_k` metric, and `measure_rag` in the evaluation script.
- `CLARITY_RETRIEVAL_FILE`, and the retriever wired in the container.

## The headline

`make eval` went from

```
UNEVALUABLE  rag.recall_at_5: not measured (gate 0.900, n=0)
```

to

```
PASS         rag.recall_at_5: 0.967 (gate 0.900, n=30)
```

A05 built the `UNEVALUABLE` status so an unmeasured gate blocks a release. This
is the first time one of those gaps has closed.

## What I could not build, and why it is not this module's fault

Plan 22 section 7 specifies pgvector with embeddings from the `embed` role for
the `full` profile, and issue #32 asks for a parity suite across the two
indexes. **There is no embedding model anywhere in the system.** Three
independent facts:

- `ModelRole.EMBED` is a declared role name with no implementation.
- `local-bge` is bound to `TemplateProvider` in the container, with a comment
  saying it is a stand-in so the chain terminates.
- `RoleRouter.invoke` returns `RoleAnswer(text=str)`. There is no shape in the
  AI layer that can carry a vector at all.

So the semantic half has no foundation, and the options were to add an
embedding model as a runtime dependency, to fake it, or to ship the seam.

**I shipped the seam**, and the parity suite with it. A deterministic lexical
"embedding" (hashed character n-grams) would have produced real vectors and a
real pgvector driver, and it would have been worth nothing: it is BM25 with
worse ranking, dressed as semantic retrieval. The point of pgvector in the plan
is semantic matching, and a vector space built from the same characters BM25
already matches on cannot do it.

What is in place instead:

- `SemanticRanker`, a protocol with no implementation, taken optionally.
- The fusion that uses it, which renormalises onto the lexical half when it is
  absent, so the lexical ordering is preserved exactly rather than halved and
  compared against zeros.
- `RetrievalTrace.semantic`, so a caller can tell a hybrid result from a
  lexical one instead of assuming. K03 composes from this and must not describe
  a lexical result as hybrid.
- `tests/contract/test_retriever_parity.py`, where the hybrid driver is
  **registered and skips**, the same way the Kafka driver skips without a
  broker. That is the useful half: the contract is written now, while the
  properties are being decided, rather than after one implementation has made
  them up.

The contract deliberately does not require an identical ordering. Two rankers
with different scoring will order near-ties differently and that is allowed.
What may not vary is which chunks are eligible at all, and what a result means.

**This needs a decision from someone who owns the dependency list**: an
embedding model is a runtime dependency with a licence to check (I17) and a
model to ship or download. Until then the `full` profile's retrieval is the same
lexical retrieval as `lite`, which is honest but is not what plan 22 says.

## Decisions made

1. **Filter before ranking, always.** A chunk the reader may not see, or that
   was not in force at the moment being asked about, is not a weak candidate:
   it is not a candidate. Scoring first and filtering after is cheaper and can
   starve a reader (if the best-scoring candidates are all staff-audience, a
   customer gets nothing while relevant chunks sit below the cut), and it makes
   a disclosure depend on a relevance score.

2. **IDF over the candidate set, not the corpus.** Given that the candidate set
   is what is being ranked, its own term statistics are the right ones: a term
   common corpus-wide but rare among the chunks in force for this reader is
   discriminating *for this query*. The cost is that scores are comparable
   within a query and not across two, which is why the cutoff is relative to
   the best hit in the same result set.

3. **The query expands, the corpus does not.** Expanding the corpus would bake
   one lexicon into stored chunks, so improving the lexicon would mean
   re-indexing everything and old chunks would keep the old expansion.

4. **A rewrite is run alongside the original, and the original wins ties.** A
   model rewrite can drop the one term that mattered. Running both means a bad
   rewrite costs latency rather than an answer, the same shape as C03's planner
   falling back to its deterministic step.

5. **`top_k` is 5 because the gate is recall@5.** A retriever tuned to a
   different k than the one it is measured at is being measured on something it
   was not built for.

6. **A query matching nothing returns nothing.** Not a weak match to fill the
   quota: K03 refuses when there is no source, and that refusal is worth more
   than a padded context.

## Four bugs the tests and the measurement found

**1. Two forms of a word folded to different stems.** The first version folded
only plural "s". Measuring the golden set showed what that cost: "travel
overseas" missed the clause saying "before travelling", and "how much I spend"
missed "spending limit". Two of three misses were one missing suffix rule, so
the rule was the fix rather than anything query-specific. recall@5 went 0.900 to
0.967.

Adding the rules then exposed the real version of the same bug: `reduced` folded
to `reduc` while `reduce` stayed `reduce`, so the two forms of one word never
met. Stripping a trailing "e" made them agree, and recall@1 went 0.767 to 0.833.

**2. The Singlish expansion put terms in the query that no document could
hold.** The lexicon is written in dictionary form ("balance", "charge") and the
index holds folded stems ("balanc", "charg"), and `query_terms` appended the raw
value. Before the "e" rule the two accidentally agreed; adding it dropped
Singlish recall from 1.000 to 0.800 and exposed it.

**3. Two lexicon entries were unreachable.** `nodanne` and `prashne` fold to
`nodann` and `prashn`, and lookup happens after folding, so those entries were
never found. The golden set did not notice: the query carrying "nodanne" also
carries "service" and "gaasthu" and passed on those. A dead lexicon entry is
invisible from the outside, which is why
`test_no_lexicon_entry_is_unreachable` asserts it directly and
`test_each_lexicon_key_actually_fires` checks every entry end to end.

The index is now keyed by the folded form, built once at import, with entries
that fold together merged rather than one silently replacing the other.

**4. A query with terms but no matches crashed.** `max()` on an empty mapping.
It was latent: the call sat inside a dict comprehension that never iterated when
there were no matches, so hoisting it for line length turned an accidentally
correct path into a visible crash. "internet is crawling in the evenings" is
exactly that case. It now returns an empty trace, which is the right answer.

All four were silent. The first three are the same shape: the index and the
query disagreeing about normalisation, which is the one thing `terms.py` exists
to prevent, and none of them failed a test until a test was written for the
mechanism rather than for the outcome.

## The remaining miss, which I am keeping

One query in thirty misses: "internet is crawling in the evenings" against a
help article written as "Data speed varies with how many connections a cell is
serving, so speeds are often lower at busy times of day". The query and the
document share **no term at all**.

I did not add `internet -> data` and `crawling -> slow` to a synonym list. That
would have chased recall to 1.000 by overfitting the golden set, and it would
have hidden the most useful thing the measurement produced: **the one remaining
miss is precisely the case lexical retrieval cannot solve**, and it is the
concrete argument for the embedding model the system does not have. A number of
0.967 with an honest miss is worth more than 1.000 with a lexicon tuned to
thirty queries.

## A finding about the gate itself

The non-vacuity probe for the Singlish lexicon is worth recording. Removing the
expansion drops Singlish recall from 1.000 to 0.600, and overall recall to
**exactly 0.900**, which still passes the gate.

So `rag.recall_at_5` on its own is not sensitive to a Singlish regression: 5 of
30 queries cannot move the overall number far enough. The dedicated
`test_singlish_recall_matches_the_english_corpus` is what catches it, and it is
gated at the same threshold. Worth knowing before anyone treats the single
overall number as sufficient. The honest fix is more Singlish and Tamil queries
in the set, which is content and needs a native speaker.

## Contract and plan notes

- **No `/v1` contract change**; the OpenAPI snapshot is unchanged.
- **The MCP `search_knowledge` tool is not switched over yet.** It still answers
  from the rule catalogue. Its contract is already the final one (query in,
  cited chunks out), so switching it is a change inside the tool with no client
  impact, but it needs a corpus to switch *to* and the registry ships empty
  (K01, I16). Doing it now would mean an MCP tool that returns nothing.
- **An architecture test needed a new category.** `BM25Index` keeps term
  frequencies in instance attributes, which
  `tests/architecture/test_module_state.py` forbids. The test's reason does not
  apply to a derived index: a module keeping a dict of cases cannot be deployed
  twice or recovered after a restart, whereas an index can be deployed twice
  (each replica builds its own from the same records) and is recovered after a
  restart (rebuilt from the repository). Losing one costs CPU, never a fact.

  So `DERIVED_INDEXES` was added, narrowly, with two conditions an attribute
  must meet: it is a pure function of committed state, and a lookup for
  something absent populates it rather than missing.
  `test_a_cold_index_scores_the_same_as_a_warm_one` asserts the second, because
  without it an index is a cache that silently serves less than the truth,
  which is business state wearing an index's name.
- **No cassette for the `extract` query rewrite.** Issue #32's acceptance 2 says
  "rewritten by `extract` (cassette)". No cassette exists in the repository at
  all and recording one needs a real provider, which this environment does not
  have; hand-writing a file into the cassette directory and calling it a
  recording would be a simulated thing not labelled as simulated (I16).

  Acceptance 2 is therefore asserted against the deterministic path, and the
  reason is ADR-0009 rather than convenience: the keyword path is the one that
  must work with no model configured, and it is what the release gate measures.
  The model assist is `RewritingRetriever`, tested with stubs for the three
  cases that matter (a rewrite that helps, one that hurts, one that raises).
  **Recording the cassette is outstanding** and needs a provider key.

## Docs updated

- This devlog, `MODULE.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, `.env.example`
  (`CLARITY_RETRIEVAL_FILE`), `docs/modules.md`, `plan.md` (#32 ticked).
- `config/ai/gates.yaml`: the `rag` gate's `min_per_language` raised from 0 to
  20, with the reason in the file. 20 is a local judgement, not a plan figure:
  at ten examples one query is ten points of recall.
- No new module edge: `"knowledge": set()` still holds.
- No new event.

## Tests run

- `make check`: **1608 passed, 544 skipped** (1548 before K02, so +60).
- `make contracts-check`: snapshot and SDK unchanged.
- `make eval`: `rag.recall_at_5` **PASS at 0.967 (n=30)**.
  `rag.citation_accuracy` stays UNEVALUABLE, correctly: nothing composes a
  grounded answer until K03.
- Acceptance 1: recall@5 0.967 against a gate of 0.900, per language
  en 0.955, si 1.000, ta 1.000, si-en 1.000.
- Acceptance 2: four Singlish queries find their clause in the top 5.
- `tests/contract/test_retriever_parity.py`: 10 pass against the lexical
  driver, 10 skip for the hybrid.
- Non-vacuity, two probes:
  - removing the Singlish expansion fails acceptance 2 and the Singlish recall
    test, and drops si-en recall to 0.600 (see the finding above about the
    overall gate not catching it).
  - filtering on the staff audience instead of the reader's fails
    `test_the_filters_are_applied_whatever_the_index`.

## Known gaps

- **No embedding model, so no semantic retrieval and no pgvector driver**
  (above). The largest gap and the one needing a decision outside this module.
- **No cassette for the `extract` rewrite** (above).
- **Two Sinhala and one Tamil query in the golden set**, which is why recall is
  reported per language but gated only overall: a per-language gate on one
  example is exactly the vacuous measurement A05's `UNEVALUABLE` exists to
  prevent. More queries per language is content work needing a native speaker.
- **No language-specific tokenisation or stemming for Sinhala and Tamil.** Both
  are agglutinative and a correct stemmer for either is a model-sized problem,
  so the index holds whole words for them. This costs recall on inflected
  Sinhala and Tamil queries and is not measurable with three examples.
- **The Singlish lexicon is a code constant with 40-odd entries**, taken from
  the `si-en` examples in the A05 intake set. It is content, not logic, and if
  intents move under the policy lifecycle in C04 (#23) it should go with them.
  **ASSUMPTION** on the romanisations: Sinhala has no standard romanisation, so
  each spelling has to be listed to be matched. **REQUIRES HUTCH CONFIRMATION**
  against real message traffic.
- `min_relative_score` and the rerank bonuses are not tuned on anything. They
  are plausible values that pass the gate, which is not the same as being right.

## Next step

K03 (#33): grounded answers. Compose from the retrieved chunks with citations,
verify every citation against what was actually retrieved and is effective and
audience-allowed, refuse when there is no source, and cache CX-approved generic
answers. `RetrievalTrace` carries the citations and the `semantic` flag it needs.

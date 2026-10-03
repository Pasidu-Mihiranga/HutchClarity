# 2026-10-03 - K01 - The knowledge source registry, and two bugs my own tests caught

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | K01 (`docs/backlog/issues/K01-knowledge-module-source-registry-and-governed-i.md`, #31), Wave 3 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.knowledge` (new: `sources.py`, `ingest.py`, `registry.py`, `repository.py`, `public.py`), `app.container`, `app.collections` |

## What changed

The `knowledge` module was a scaffold with an empty `public.py`. It now has:

- **`sources.py`**: `KnowledgeSource`, one record per `(source_id, version)`,
  with `owner`, `audience`, `language`, `effective_from/to`, `product_ids` and
  `kind`; and `Chunk`, the retrievable unit, carrying all of that plus a
  `clause_ref` and a `citation`.
- **`ingest.py`**: clean, check the script against the declared language, chunk
  by structure.
- **`registry.py`**: `KnowledgeRegistry.publish`, `supersede`, `source_as_of`,
  `versions` and `chunks_as_of`.
- **`repository.py`**: the `knowledge.sources` and `knowledge.chunks`
  collections.
- Wired in `app.container` as `clarity.knowledge`.

## Why

Issue #31. Help articles lived in the mock store with keyword scoring, and
`KNOWLEDGE_QA` has no corpus to answer from.

## Decisions made

1. **Two versions may not be in force at once, and that is a refusal.** "Old
   versions stay retrievable for what applied then" (plan 20 section 167) only
   means something if exactly one version answers "then". With an overlap
   allowed, retrieval has to break a tie, and the answer to a question about
   March would depend on which record happened to be written first.

   The cost is that publishing v2 means closing v1, which is bookkeeping nobody
   should have to remember, so `supersede` does both in one unit of work. One
   unit on purpose: a crash between closing the predecessor and publishing the
   successor would leave a period covered by nothing, and a question about that
   period would get silence rather than the text that was really in force.

2. **Windows are half-open.** `effective_from` inclusive, `effective_to`
   exclusive, so the instant a successor starts is the instant the predecessor
   stops: no gap, no overlap, no off-by-one about midnight.

3. **Nothing is returned for a moment before the first version existed.** The
   tempting fallback is the earliest version, and it is wrong: it answers a
   question about an uncovered period with text that did not apply. I2, missing
   evidence is a person and never a guess.

4. **Audience is filtered in three independent places**, because its failure is
   a disclosure rather than a wrong answer. An SOP quoted to a customer can
   name thresholds and escalation paths that exist precisely because customers
   do not see them. So: `Audience.may_read` is asymmetric (customer content is
   readable by everyone, staff content only by staff), `chunks_as_of` takes
   `audience` keyword-only **with no default**, and `SourceKind.STAFF_SOP`
   cannot be published as customer audience at all.

   No default on purpose. `audience: Audience = Audience.CUSTOMER` is the safe
   direction and still wrong: the caller who should have passed `STAFF` gets
   silently empty results, and the caller who forgot is never found.

5. **Filter before ranking.** `chunks_as_of` is a metadata filter and nothing
   else. An effective-date or audience mistake is a disclosure or a wrong
   answer about the law, and neither should be able to depend on a relevance
   score or a top-k cutoff. K02 ranks what this returns.

6. **Chunks are stored, not derived on read.** Ingestion is deterministic, so
   re-chunking would give the same answer today. But a published version's
   chunks are what an answer cited, and changing the chunker must not
   retroactively change what a citation from last March points at.

7. **Metadata is copied onto every chunk rather than looked up through the
   source.** A filter that has to join to decide is a filter that gets skipped
   when the join is inconvenient, and the copy stays truthful about the version
   it came from once a successor exists.

8. **Owner, effective date and audience are required with no defaults.** A
   source nobody is accountable for should not be quotable to a customer, and
   nobody should acquire an audience by forgetting to set one.

9. **The registry ships empty.** The corpus is HUTCH content: catalogue, T&C,
   Gazette 2316/14, help articles. Writing any of it would be inventing HUTCH
   regulations and numbers, which I16 forbids. **REQUIRES HUTCH CONFIRMATION**
   for the real corpus; the tests publish their own synthetic sources.

## Why chunk boundaries are a correctness concern

An answer has to cite `source_id@version#clause`. A fixed-size window cuts
across clause boundaries, so a chunk holding the end of 4.1 and the start of 4.2
can honestly cite neither, and K03's citation verifier would be checking a
reference that does not identify the text it came from. So legal text is split
per clause, and length only applies *within* a clause, where the pieces keep
their reference and overlap so a sentence on the seam is still findable.

The clause pattern is anchored to the line start. Unanchored, "Subject to 4.2
below, the pack renews monthly" splits mid-sentence and produces a chunk
beginning "4.2 below, the pack renews monthly" which would then be cited as
clause 4.2 while actually being part of 4.1. There is a test for exactly that
sentence.

A preamble keeps an empty clause reference: dropping it loses real text, and
numbering it invents a reference.

## Two bugs my own tests caught

**1. Singlish was unpublishable.** The script check refused any disagreement
between the detected script and the declared language. That is right in one
direction and badly wrong in the other: Sinhala script in a document declared
`en` is unambiguously a mistake, but **Latin script in a document declared `si`
is Singlish**, which is how a great many customers write and which C04 (#23)
exists to support. A symmetric check made a Singlish knowledge source
impossible to publish. The check is now asymmetric, and the test that found it
(`test_singlish_is_not_refused_as_a_mismatch`) says why in its docstring.

**2. A catalogue entry was being split after all.** The ingest path chose
`pieces = [("", body)]` for a catalogue source and then passed every piece
through the length window, so a long offering was split anyway, which is exactly
what the one-chunk-per-offering rule exists to prevent: a question about the
price can retrieve the piece that does not mention the price. The windowing
function is now chosen per kind.

Both were found by writing the test from the plan's wording rather than from the
code I had just written.

## A note on token counts

Plan 22 section 7 specifies 300 to 500 tokens per chunk with 10 to 15 percent
overlap. The implementation counts **words**, and the constants are named
`WORDS_PER_CHUNK` and `WORDS_OF_OVERLAP` rather than `TOKENS_*` so nobody reads
them as exact. A word count runs roughly 25 to 35 percent under a subword
tokeniser for English and further under for Sinhala and Tamil, so the window is
approximate. That is a deliberate trade: no tokeniser becomes a runtime
dependency, and the number decides retrieval quality rather than an outcome for
a customer.

## Docs updated

- This devlog, `backend/src/clarity/modules/knowledge/MODULE.md` (replacing the
  scaffold stub), `CHANGELOG.md`, `ARCHITECTURE.md` (gap 7 rewritten for C03 and
  K01), `docs/modules.md`, `plan.md` (#31 ticked).
- **No new module edge.** `"knowledge": set()` still holds: the registry
  depends only on the kernel and `platform.persistence`. Nothing calls it yet
  except the composition root.
- **No new event**, deliberately. Plan 22 section 7 specifies
  `knowledge.published` to invalidate the semantic cache and re-index affected
  chunks. Neither the cache nor the index exists until K02 and K03, so
  declaring it now would be a contract to maintain with no consumer. It belongs
  with whichever of those introduces the thing that has to react.
- No `.env.example` change: nothing new is configurable by environment.
- No `/v1` contract change; the OpenAPI snapshot is unchanged.

## Tests run

- `make check`: **1548 passed, 534 skipped** (1513 before K01, so +35).
- `make contracts-check`: snapshot and SDK unchanged.
- Acceptance 1 (`test_knowledge_versions.py`): a T&C clause version 2 effective
  next month, retrieval for today returns version 1, with version 1's text and
  version 1's citation. Plus the other half (version 2 once it is in force),
  the dispute case (March's terms, asked in October), the uncovered period, the
  overlap refusal, supersession and republication.
- Acceptance 2 (`test_knowledge_audience.py`): a staff SOP is never retrieved
  for a customer, asserted on the whole in-force corpus rather than on a
  ranking, and checked for the SOP's actual content ("duty manager", the
  threshold) rather than only its id. Plus the other half, that a staff reader
  sees both, so the filter cannot be "return nothing".
- `test_knowledge_ingestion.py`: chunking, the cross-reference case, the
  preamble, catalogue, over-long clauses, NFC normalisation, zero-width
  stripping, script detection in all three languages, Singlish, and the full
  metadata set.
- Non-vacuity, two probes:
  - removing the audience filter fails acceptance 2 and nothing else.
  - removing the effective-date filter fails acceptance 1 and four other
    version tests.

## Known gaps

- **Not under the governance change lifecycle.** Plan 20 makes a knowledge
  source a kind K2 artefact: draft, review, publish, with Legal and Compliance
  as approvers. `publish` enforces the mechanical half (owner present, window
  non-overlapping, language consistent, text chunkable) but does not go through
  `PolicyGovernance`, so there is no maker-checker gate on new legal text. This
  is the module's largest gap and the same remaining half of the M-GOV
  dependency that C02 recorded for flows.
- **No corpus** (above). **REQUIRES HUTCH CONFIRMATION.**
- The MCP `search_knowledge` tool still answers from the rule catalogue. Its
  contract is already the final one, so K02 swaps the backend without touching
  the tool surface or any client.
- `clause_prefix` is per source and free text. A reference like `T&C 4.2` is
  only as consistent as whoever published it; if citations become something
  customers quote back, the prefix should come from the source kind.
- No language-specific tokenisation or stemming, which will matter for Sinhala
  and Tamil BM25 in K02.

## Next step

K02 (#32): the index and retrieval. BM25 in `lite`, pgvector hybrid in `full`,
ranking over the `chunks_as_of` candidate set, with the filters staying where
they are.

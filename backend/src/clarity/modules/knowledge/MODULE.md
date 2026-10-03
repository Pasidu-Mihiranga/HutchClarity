# knowledge - MODULE.md

| Field | Value |
|---|---|
| Kind | module |
| Layer | L4 domain (`clarity.modules.knowledge`) |
| Deployable | `clarity-api` today (modular monolith); a candidate for extraction (plan 21 section 179) |
| Owner | TBD |
| Status | built (`lite` and `full`): source registry and governed ingestion, K01 (#31), 2026-10-03. Retrieval is K02 (#32), grounded answers K03 (#33) |
| Files | `sources.py`, `ingest.py`, `registry.py`, `repository.py`, `public.py` |

## 1. Purpose

Governed knowledge content: the product catalogue, T&C clauses, VAS rules,
Gazette text, help articles, CX-approved answers and staff SOPs (plan 22
section 7).

The module's job is not search. It is to make sure that what gets quoted to a
customer is **attributable and was actually in force**: every source version has
an owner, an effective window, an audience and a language, old versions stay
readable, and every retrievable chunk carries enough metadata to be filtered
without a join.

`KnowledgeRegistry` is the way in and the way out. Publish a version; read back
the chunks in force at a moment for a given audience.

## 2. Public surface (`public.py`)

`KnowledgeRegistry`, `KnowledgeRepository`, `StoredKnowledgeRepository`,
`KnowledgeSource`, `Chunk`, `Audience`, `SourceKind`, `PublicationRefused`,
`IngestionRefused`, `ingest`, `check_language`, `clean`, `dominant_script`,
`publish_all`, `SOURCES`, `CHUNKS`, `WORDS_PER_CHUNK`, `WORDS_OF_OVERLAP`.

## 3. Used by

`clarity.app.container`, which constructs the registry. Nothing else yet: K02
(#32) adds the index and retrieval over `chunks_as_of`, and K03 (#33) the
grounded answer and citation verifier. The MCP `search_knowledge` tool still
answers from the rule catalogue (see Known gaps).

## 4. Depends on

| Package | Through |
|---|---|
| `clarity.kernel.common` | `ClarityModel`, `Language`, `utc_now` |
| `clarity.kernel.ids` | `new_id` |
| `clarity.platform.persistence` | `Repository`, `UnitOfWork`, `UnitOfWorkFactory`, `MemoryStore` |

No synchronous call to another module (`"knowledge": set()` in
`tests/architecture/test_module_dependencies.py`), and no module edge added by
K01.

## 5. Data owned

| Collection | Holds |
|---|---|
| `knowledge.sources` | One record per `(source_id, version)`, keyed `source_id@version` |
| `knowledge.chunks` | The chunks ingested from each source version |

One PostgreSQL schema and role in the `full` profile (`knowledge`), in-memory in
`lite`. Chunks are **stored rather than derived on read**: ingestion is
deterministic, so re-chunking would give the same answer today, but a published
version's chunks are what an answer cited, and changing the chunker must not
retroactively change what a citation from last March points at.

### Metadata on every chunk

`source_id`, `version`, `clause_ref`, `effective_from`, `effective_to`,
`language`, `product_ids`, `audience`, `owner`, `kind`, `ordinal` (plan 22
section 7). Copied from the source, not looked up through it: a filter that has
to join to decide is a filter that gets skipped, and a copy stays truthful about
the version it came from after a successor is published.

## 6. Invariants

- **One version in force at a time.** Publishing a version whose effective
  window overlaps a sibling's is refused. "What applied then" only means
  something if exactly one version answers it; the alternative is retrieval
  breaking a tie and the answer to a question about March depending on which
  record was written first.
- **Old versions are kept, never replaced.** A correction is a new version,
  because the old one may already have been cited in a receipt or a reply.
- **Windows are half-open**: `effective_from` inclusive, `effective_to`
  exclusive, so a successor starting the instant its predecessor ends leaves no
  gap and no overlap. `supersede` does both halves in one unit of work.
- **A staff SOP is never returned to a customer reader.** Three independent
  places: `Audience.may_read` is asymmetric, `chunks_as_of` requires the
  audience argument with no default, and `SourceKind.STAFF_SOP` cannot be
  published as customer audience at all.
- **Nothing is returned for a moment before the first version took effect.**
  Falling back to the earliest version would answer a question about an
  uncovered period with text that did not apply (I2).
- **A source has an owner, an effective date and an audience, all required.**
  No defaults: a source nobody is accountable for should not be quotable, and
  nobody should get an audience by forgetting to set one.
- **Script is checked against the declared language, asymmetrically.** Sinhala
  or Tamil script in a document declared `en` is refused. Latin script in one
  declared `si` or `ta` is **not**, because that is Singlish or romanised
  Tamil, which is how many customers write (C04, #23).
- **No chunk spans two clauses.** An answer cites
  `source_id@version#clause`, and a chunk straddling a boundary can honestly
  cite neither, which would leave K03's citation verifier checking a reference
  that does not identify its text.
- **A catalogue entry is one chunk**, whatever its length. An offering is the
  unit someone asks about; split up, a question about the price can retrieve
  the piece that does not mention the price.
- Time comes from the injected clock (I11). `chunks_as_of` takes the moment
  explicitly, and for a dispute that moment is the event time, not now.
- Simulated content is labelled (I16). The registry ships **empty**: the corpus
  is HUTCH content and inventing T&C or Gazette text would be inventing HUTCH
  regulations.

## 7. Migration status (enterprise-plan 21)

R6. The registry and ingestion are in place; the index, the hybrid score and the
rerank are K02, and the grounded answer, citation verifier and semantic cache
are K03.

**Not yet under the governance change lifecycle.** Plan 20 makes a knowledge
source a kind K2 artefact: draft, review, publish. Today `publish` enforces the
mechanical parts of that (owner present, window non-overlapping, language
consistent, text chunkable) but does not go through `PolicyGovernance`, so there
is no maker-checker gate on new legal text. That is the same remaining half of
the M-GOV dependency that C02 recorded for flows, and it is the module's largest
gap rather than an oversight.

## 8. Events

None produced or consumed yet. Plan 22 section 7 specifies a
`knowledge.published` event to invalidate the semantic cache and re-index
affected chunks. Neither the cache nor the index exists until K02 and K03, so
the event is deliberately not declared here: an event with no consumer is a
contract to maintain for nothing. It belongs with whichever of those introduces
the thing that has to react.

## 9. Tests

- `backend/tests/unit/test_knowledge_versions.py` - effective dating, supersession, overlap refusal (K01 acceptance 1)
- `backend/tests/unit/test_knowledge_audience.py` - audience filtering, in all three places it is enforced (K01 acceptance 2)
- `backend/tests/unit/test_knowledge_ingestion.py` - cleaning, script detection, structure-aware chunking, metadata

## 10. Change history

| Date | Devlog entry | Summary |
|---|---|---|
| 2026-10-02 | `docs/devlog/2026/2026-10-02-R1-dev-merge.md` | Scaffold: `public.py` and `MODULE.md` stubs to satisfy the architecture tests |
| 2026-10-03 | `docs/devlog/2026/2026-10-03-K01-knowledge-source-registry.md` | Source registry, effective dating, audience filtering and governed ingestion |

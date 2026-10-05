# 2026-10-05 - Workstream F - AI credibility

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga |
| Work package | Workstream F (F1, F2, F4, F5; F3 measured and still red) |
| PR / commit | feat/ai-credibility |
| Units touched | `clarity.ai`, `clarity.modules.knowledge`, `clarity.app`, `backend/scripts`, `config/ai` |

Written by an AI coding agent (Claude Code) under AGENTS.md §12.

## What changed

### F4 - the `embed` role has an implementation

`ModelRole.EMBED` was a declared name with nothing behind it, and the reason was structural rather than neglect: `RoleRouter.invoke` returns text and a vector is not text, so the embed role could not be invoked through the seam every other role uses.

- **`clarity/ai/embedding.py`** (new): the `Embedder` port, `HashingEmbedder` (the local driver), `fit_idf` and `cosine`. Deterministic via `blake2b`, because `hash` is salted per process and replay has to be exact (I11). A subprocess test proves it.
- **`clarity/modules/knowledge/semantic.py`** (new): `VectorSemanticRanker`, the first implementation of the `SemanticRanker` protocol, caching chunk vectors by chunk id and fitting IDF from the published corpus. Exported through `public.py` (I5).
- **The container** wires it beside the lexical index and refits on every corpus republish, so both halves rank the same world.
- **`hybrid.min_semantic`** (new config key): an absolute cosine floor. Needed because turning the semantic half on *removed* a safety the lexical-only retriever had for free, see below.
- **`scripts/evaluate.py`** now builds the hybrid retriever, so the gate measures what the deployment runs rather than a lexical-only one nobody ships.

### F1 - cassettes can be recorded

`scripts/record_cassettes.py` (new) plus `make cassettes` and `make cassettes-dry`. It builds the prompts the system actually sends for `extract`, `guard` and `reason` (including the planner prompt, in `validate_plan`'s real JSON grammar), calls the configured provider once per prompt and writes the recordings.

**No cassettes are committed by this change, and that is the point.** Recording needs a real provider key, which this environment does not have. The script refuses without `CLARITY_RECORD_CASSETTES=1` and refuses when no provider is configured; there is no `--offline` mode and no placeholder mode. A cassette whose `response` a developer typed is not a recording of anything, and a suite replaying one asserts what somebody imagined a model would say, which is the failure mode this repository exists to argue against.

### F2 - the bounded agent step runs

`tests/unit/test_agent_planner.py` (new, 11 tests). `_planner` returns `None` without a remote `reason` model, so `BoundedAgent`'s loop had never executed in CI: every existing test asserts the `NO_PLANNER` fallback. These drive it through a `ScriptedPlanner` test double and pin the agent's half of the I1 contract - a well-formed plan runs its tool, the result comes back delimited as untrusted, and a plan naming a tool the state did not declare, carrying an amount, missing a reason code, or written as prose changes nothing about the turn.

A test double rather than a cassette, for the reason in F1, and it is named for what it is. When cassettes exist the same assertions run against a real answer through `_RolePlanner` with nothing here changing.

### F5 - the corpus is no longer English-only

The five simulated help articles now exist in Sinhala and Tamil as well (15 sources, 5 per language). K03 quotes a retrieved clause verbatim, which is what makes a citation checkable, and the consequence was that a Sinhala customer asking in Sinhala got a correct answer quoting English. Retrieval already prefers the query's language without filtering the others out, so a Sinhala question still reaches an English-only clause when that is all there is.

## F3 - measured, and the gate is still red

The plan allows "improve retrieval **or** move the threshold with a documented reason". The retrieval was improved and it was not enough, so the threshold has **not** moved. What was measured:

| retriever | citation_accuracy | recall@5 |
|---|---|---|
| lexical only (before) | 0.931 | 0.967 |
| hybrid, no score floor | 0.900 | **1.000** |
| hybrid, floor at 0.25 (shipped) | 0.931 | 0.967 |

Three findings, all recorded in `config/ai/gates.yaml` and `config/ai/retrieval.yaml` so nobody repeats the experiment:

1. **The two failing queries are a synonym gap, not a morphology gap.** `turned on` shares no substring with `activated`; `crawling in the evenings` shares none with `speed may be reduced`. A hashed n-gram space cannot connect those and no tuning of it will. It *can* connect `renewed` to `renewal`, which BM25 scores at zero, and there is a test for each of those two facts.
2. **The local embedder's signal sits inside its own noise band.** Measured over this corpus: unrelated clause pairs have median cosine 0.089 and p90 0.250, and deliberately irrelevant questions ("recipe for chicken curry") reach 0.107 to 0.202 against their best match - while `SIM-HELP-NETWORK-SLOW`, the *correct* answer for the evening-speeds query, scores 0.214. Relevant and irrelevant overlap, so no floor separates them.
3. **Turning the semantic half on without a floor is worse than leaving it off.** With no floor, recall@5 reaches a perfect 1.000 and citation accuracy *drops* to 0.900, because queries that previously returned no sources (and were honestly refused) now ground themselves on an unrelated clause. `min_relative_score` cannot catch this: it is a share of the best hit, so it cannot tell "all weak" from "one strong". Hence the absolute floor, set at 0.25 from the noise measurement above rather than against the golden queries.

So the gate stays at 0.98 and stays failing. Lowering it to the number we achieve is the one move the gate layer exists to refuse, and 0.98 over 29 answered queries means "no wrong citations", which is the right bar for a product whose promise is a checkable citation.

## Decisions made

- **No heavy ML dependency.** A learned multilingual embedder (plan 19 §2.1 names BGE-M3) means torch, which breaks `lite`'s "Python only, no services" (ADR-0006) and an offline-safe build. The port accepts one; the default does not pull one. Licence check not needed: nothing was added to the runtime path (I17).
- **IDF is in, although it scores one query worse on the golden set.** Unweighted, the space measures "written in English" more than topic, and two unrelated clauses look similar because both contain "the" and "charge". IDF is the standard correction. Choosing the unweighted variant because it happens to score 0.9333 against 0.9000 on 30 examples would be fitting the model to its own test, and the difference is one query.
- **The floor was derived from the noise band, not the gate.** Same reason.
- **`fit` is duck-typed, not in the `Embedder` protocol.** A remote model is already trained and has nothing to fit; putting `fit` in the port would make every driver implement a no-op to satisfy it.
- **No pgvector driver yet.** F4 asks for one for `full`. The port and the ranker are what a pgvector driver plugs into, and writing one now would be writing a store for vectors from an embedder whose limits are the reason the gate still fails. Deferred deliberately rather than forgotten; recorded below.

## Docs updated

- [x] This devlog
- [x] `config/ai/gates.yaml` (the citation_accuracy diagnosis, replaced with the measurement)
- [x] `config/ai/retrieval.yaml` (the hybrid comment, and the new `min_semantic` key with its derivation)
- [ ] `clarity/modules/knowledge/MODULE.md`: updated in this change for the new public name
- [ ] ADR: an ADR for "the embed role is a port with a local non-learned driver" is arguably owed. Not written; flagged for the next pass.
- [ ] CHANGELOG.md: n/a (no `/v1` change)

## Tests

- `tests/unit/test_embedding.py` (new, 14) and `tests/unit/test_agent_planner.py` (new, 11): all pass.
- `pytest -k "knowledge or retrieval or rag or cassette or embed"`: 164 pass, 1 skip.
- `make eval`: runs, `rag.recall_at_5` PASS 0.967, `rag.citation_accuracy` FAIL 0.931. Unchanged, as above, and `make eval` still exits non-zero.
- **Not run:** the full `make check`. The user asked for this workstream quickly and explicitly not to run the wider suite; the blast radius (knowledge, retrieval, the container's wiring, the architecture and unit suites) was run instead.

## Open issues / next step

1. **A learned multilingual embedder** behind the `Embedder` port is what closes `rag.citation_accuracy`. Nothing else in F moves it.
2. **The pgvector driver for `full`** (the rest of F4).
3. **Record the cassettes** with a real key, then F2's assertions can run against a real planner answer.
4. **F3 is not closed.** `make eval` still exits non-zero, by choice.
5. The other gates block on dataset size (intake wants 300 per language and has 20) and on the human-rated language review, neither of which F touches.

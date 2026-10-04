# 2026-10-04 - C3 (F04, F11) - a persona port, three drivers, and the I1 boundary

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code, for Pasidu Mihiranga |
| Work package | C3 (workstream C, plan items F04 and F11) |
| PR / commit | branch `feat/foresight-persona-engine`, stacked on C1 |
| Units touched | foresight, app/container, interfaces/http (demo route) |

## What changed

- **Retired `swarm.py`** and with it `ScenarioRehearsal`, `SeededPersonaSimulator`, `SwarmReport` and `Comparison`.
- **New `personas.py`:** the `PersonaSimulator` port returning `PersonaRun` of `Propensity` values in [0, 1], plus three drivers: `StatisticalBaseline`, `RoundBasedPersonaSimulator`, `LlmPersonaSimulator`. Also `PersonaRouter` / `RoleRouterPersonas`, the narrow seam onto the AI layer.
- **New `rehearsal.py`:** `PersonaRehearsal`, `RehearsalReport`, `PairComparison`.
- **`simulation.py`:** `Foresight` now reaches the baseline through the port, so the reported `relative_score` and a comparison's headline column are the same arithmetic rather than two copies. New `score_of(propensity, share_of_base)`.
- **`catalogue.py`:** `PersonaRounds` and `persona_rounds(as_of)`.
- **`config/policy/foresight.yaml`:** five new keys for the round-based driver.
- **`app/container.py`:** `foresight_rehearsal`, with `_persona_comparison` choosing the LLM driver when a remote `reason` model is configured and the round-based one otherwise.
- **`interfaces/http/main.py`:** the demo route reports the comparison column and an agreement rate. Response keys unchanged apart from two additions.
- **New ADR-0043.**

## Why

Plan C3: "`swarm.py` today is `sha256(seed:scenario:theme:segment)[:2] % 3 - 1` applied to the baseline, compared against a second run of that same baseline. It measures a hash."

That is exactly right and worth restating, because the old tests passed. They asserted that the same seed reproduces the same output, which is true of any hash and says nothing about personas, complaints or the change being rehearsed. Plan 08 §12.9 asks for a statistical baseline *alongside* a simulation; what existed was a baseline alongside a permutation of itself.

## Decisions made

- **The port returns propensities, never bands and never counts.** A band is the output of a threshold, so two drivers that band their own numbers can disagree because they banded differently rather than because they expect different things. A count is a claim about volume none of these methods supports.
- **A propensity is per segment, not per subscriber base.** This is what makes the methods comparable at all: a cohort simulation naturally answers "how many of this segment complained", so the baseline's segment-share factor moved out of the method and into `score_of`. The reported `relative_score` is unchanged, and C1's tests passing untouched is the evidence.
- **The I1 boundary is structural (ADR-0043).** `PersonaRehearsal` constructs its own `StatisticalBaseline`; it is not a constructor argument. The only injectable driver is `comparison` and its output only reaches the comparison column. A test inspects the constructor signature, and another wires a driver answering `1.0` everywhere and asserts the reported bands do not move. The repository already has a case of a rule that held only because one of two drivers happened to be wrapped (B7's OPA `granted` field); the lesson was to make enforcement structural.
- **The round-based driver uses integer draws against integer thresholds**, so a propensity is an exact ratio of two counts and no float ever enters one. That is I3's instinct applied outside the money path.
- **One random stream per theme-segment pair**, seeded from the run seed and the pair, so adding a theme does not silently move another theme's numbers. A test asserts a pair shared between two change types keeps its value.
- **`pressure_scale` is set so the two deterministic drivers land within about 20% of each other** on the demo segments. Not to make them agree: so that a disagreement means the methods disagree rather than that their units do. A test pins the median ratio inside a wide band.
- **An absent comparison is not a zero one.** A driver that could not answer reports `answered=False` and the column is `None`. A column of zeros reads as the finding that no segment will complain.
- **`agreement_rate` is reported and declared meaningless** in the same report. Both methods rest on the same segment catalogue and neither has been calibrated. Reporting it without the caveat would let a reader infer confidence from a high number.
- **The LLM driver drops rather than defaults.** A pair the model did not answer for, or answered with `1.5` or `"high"`, has no estimate; substituting zero would turn a non-answer into a finding. The caveat says how many were dropped.
- **The prompt is narrow and the facts are aggregates only.** A test asserts the fact keys are exactly the seven expected and that nothing customer-shaped appears. The system prompt forbids recommendations, amounts and counts.
- **Because the personas are written here rather than adopted from MiroFish/OASIS/Zep, plan 04 T8's licence gate does not apply.** No new dependency: the round-based driver uses `random` from the standard library.

### No cassette yet, deliberately

The plan asks for "recorded cassettes so `make check` never makes a live call". The driver is built to work with `ai/cassettes.py` through the composition root, and `make check` makes no live call: the container only wires `LlmPersonaSimulator` when a remote provider is configured, and in CI none is.

The tests use a `StubRouter` that **says it is a stub**. Hand-writing a cassette file would present an authored answer as a recorded one, which is what I16 forbids, and `ai/cassettes.py` is explicit that a cassette holds "the answer that came back". Recording a real one needs a live provider and is plan item F1's job. This is flagged rather than quietly papered over.

## Docs updated

- [x] `MODULE.md` of: foresight (files, public surface, the C3 breaking-change table, invariants, tests, history)
- [x] This devlog
- [x] `CHANGELOG.md`
- [x] **New ADR-0043** and `docs/adr/README.md` index
- [ ] `docs/modules.md` / `ARCHITECTURE.md`: not needed. No new module and no new dependency between modules. Foresight now imports `clarity.ai` through its own narrow protocol, which is L4 importing L3 and allowed by I4.
- [ ] Plan via `CHANGES.md`: not needed for C3.
- [ ] Walkthrough: not needed. `GET /v1/demo/foresight` gained two keys inside `simulation` and `baseline_vs_swarm.swarm` can now be `null`; no flow changed.

## Tests

- `tests/unit/test_foresight_personas.py`: **53 new tests**, replacing the 3 in `test_foresight_swarm.py`. A parity suite parametrised over all three drivers (every pair answered, every value in range, no band or count attribute, version and basis stated, aggregates-only basis), the round-based driver's determinism, per-pair streams, policy-driven rounds and cohort size and exact-ratio arithmetic, the LLM driver's JSON parsing, fenced blocks, dropped values, unknown keys and no-answer path, prompt contents, and the I1 boundary.
- `make check`: **2649 passed, 640 skipped**, ruff, mypy --strict over 247 files, import contracts 3 kept 0 broken. C1's branch was 2599 passed; this is +53 new and -3 deleted.
- C1's existing foresight tests pass untouched, which is the evidence that routing the engine through the port did not change a reported number.

One pre-existing test fails under this session's network proxy and passes without it: `tests/unit/test_cassettes.py::test_an_outbound_connection_is_refused`. Unrelated.

## Open issues / next step

- **F1 owes a real cassette** for the persona prompt. Until then the LLM driver has never spoken to a model.
- The LLM driver sends one prompt for every pair in a scenario. On a twelve-pair rehearsal that is fine; on a much larger segment catalogue it would want batching, and the prompt has no guard against growing past a context window.
- `_persona_comparison` picks the LLM driver whenever a remote `reason` model is configured. There is no way yet for an operator to ask for the round-based one instead; that wants a switch (`platform/config/switches`) when somebody needs it.
- C4 should expose the comparison column on the real API, not only on the demo route.

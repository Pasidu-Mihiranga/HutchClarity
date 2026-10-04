# 2026-10-04 - C1 (F03) - foresight parameters become policy, Scenario becomes a value

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code, for Pasidu Mihiranga |
| Work package | C1 (workstream C, plan item F03) |
| PR / commit | branch `feat/foresight-policy-scenario` |
| Units touched | foresight, platform/content, platform/config (data only), app/container, interfaces/http |

## What changed

- **New `config/policy/foresight.yaml`.** Eleven keys: the segment catalogue, five per-change-type theme catalogues, the borrowing map, two band thresholds and the calibration gate. Catalogues are CSV strings (rows on `;`, fields on `|`) because the resolver coerces money, number, bool and string only; `config/policy/proactive.yaml` already takes that escape hatch.
- **New `backend/src/clarity/modules/foresight/catalogue.py`.** The one place that turns resolver answers into typed values. Owns `ChangeType`, `Segment`, `ThemeWeight`, `ThemeCatalogue`, `Bands` and `CatalogueInvalid`.
- **New `backend/src/clarity/platform/content/foresight.py`.** Mitigation lines, named caveats and the two basis strings, beside the `_CAUSE` precedent in `templates.py`.
- **`simulation.py`:** `Foresight(catalogue, clock=None)`. `Scenario` is frozen, `scenario_id` is a field, `effective_date` is a required `date` and drives `as_of` for the whole run. `ForesightReport` gained `scenario_id`, `effective_date` and `generated_at`.
- **`backtest.py`:** `Backtest(catalogue, clock=None)`; the gate resolves from policy; `MIN_REAL_LAUNCHES` is gone.
- **`swarm.py`:** `ScenarioRehearsal(catalogue)` and `SeededPersonaSimulator(catalogue)`.
- **`app/container.py`:** builds `foresight_catalogue`, `foresight` and `foresight_backtest`, with the container clock.
- **`interfaces/http/main.py`:** `GET /v1/demo/foresight` uses the container's engine instead of constructing its own. Response shape unchanged.

## Why

Plan workstream C, item C1: "Every tunable is in Python today: `DEMO_SEGMENTS`, `_THEMES` weights, `_THEME_ALIASES`, band thresholds `_HIGH`/`_MEDIUM`, `MIN_REAL_LAUNCHES`, and all mitigation and caveat wording." That is I10 inverted, and D2 specifically: a constant beside a policy value is the one that gets read by mistake. A product manager could not change a band threshold or add a segment without a release.

Two defects the plan names were fixed on the way:

1. **`Scenario.scenario_id` was a `@property` calling `new_id`**, so every read returned a different id. Nothing could store, compare or cite a scenario, which is also why nothing stored one. C2's persistence rests on it being a field.
2. **`effective_date` was an optional free-text string that nothing read.** It is now a required `date` and it is what the run resolves policy at. A rehearsal is about a change that lands on a day, so the parameters it uses are the ones in force on that day.

## Decisions made

- **Wording in `platform/content`, numbers in the policy store.** A mitigation line is prose approved once and reused; a band threshold is scoped, effective-dated and resolved per run. Putting prose in the policy store would make every wording fix a scoped artefact version; putting thresholds in content would hard-code policy.
- **One theme key per change type**, not one key holding all five. A product manager changing what a price increase produces should be approving a diff about price increases.
- **Borrowing is declared and reported.** Seven of twelve change types have no catalogue of their own. That was a silent Python dict, so a reader of a `new_pack` rehearsal could not know they were looking at pack-retirement themes. The map is policy now and the report names the lender in its caveats.
- **Borrowing follows one level only.** A chain of aliases ends up reading a catalogue three hops from the change asked about, and nobody reviewing the policy file would see it. A chain raises `CatalogueInvalid`.
- **The theme driver is an allowlist** checked at parse time. `getattr(segment, driver)` on an unchecked policy string would let a typo silently scale by 1.0, and would let a policy value name any attribute of the dataclass.
- **A malformed catalogue raises rather than defaults.** A run over half a parsed segment list reports numbers nobody authored, in the same shape as a correct run.
- **A change type with no themes and no alias produces an explicit caveat.** An empty report and "we expect no complaints" otherwise look identical on screen.
- **The calibration gate resolves as of the moment the backtest runs**, not as of any launch: the question is "may we rely on this engine now", governed by the rule in force now.
- **The gate key is tagged `regulatory`**, so `class_for` derives change class C4 and lowering it needs a second approver, with a guardrail that refuses a value under three. Raising the bar is routine; lowering it is how a synthetic backtest would be made to look like evidence.

### Known gap, carried to C6

`Guardrail.permits` returns `True` for any value that is not `Decimal | int`, and policy values are quoted strings in YAML, so the `min: 3` guardrail does **not** currently bite at load. The key and the guardrail are declared here; making it actually refuse is one of C6's four locks, where the test for it belongs. This is pre-existing and affects every quoted-number guardrail in the repository, not just this one.

## Docs updated

- [x] `MODULE.md` of: foresight (public surface, the breaking-change table, dependencies, invariants, tests, history)
- [x] This devlog
- [x] `CHANGELOG.md` (the module's public surface changed)
- [ ] ARCHITECTURE.md / modules.md: not needed, no new module and no new dependency **between modules**. Foresight stays a leaf; its new dependencies are on L2 platform packages.
- [ ] Walkthrough: not needed, no user-visible flow changed. `GET /v1/demo/foresight` returns the same shape.
- [ ] Plan via CHANGES.md: not needed for C1. Plan 10's `/v1/simulation/...` contradiction is C4's to fix, where the route is actually added.
- [ ] ADR: none. C1 implements decisions the plan already records; the two that would warrant one (the absolute calibration gate, the persona port's I1 boundary) belong to C6 and C3.

## Tests

- `tests/unit/test_foresight_catalogue.py`: 39 new tests. Policy-driven parameters, `as_of` resolution across two effective windows, every parse refusal, one-level borrowing, the frozen scenario and its stable id, the injected clock, and a parametrised check that all twelve change types resolve to a catalogue.
- `tests/unit/test_autopsy_foresight.py` and `tests/unit/test_foresight_swarm.py`: updated for the new constructors. Behaviour under test is unchanged; the helpers at the top of each file are the whole of the change.
- `pytest`: `2599 passed, 640 skipped` (was 2560 passed before this change).
- `ruff check`, `ruff format`, `mypy --strict` (246 files), `lint-imports` (3 kept, 0 broken): clean.

One pre-existing test fails under this session's network proxy and passes without it: `tests/unit/test_cassettes.py::test_an_outbound_connection_is_refused` asserts on how a blocked connection is refused, and the proxy refuses it differently. Unrelated to this change.

## Open issues / next step

- C2: persistence. Seven collections, `"foresight": "foresight"` in `OWNERS`, six append-only. It needs `scenario_id` to be a real field, which is why C1 came first.
- The guardrail gap above, in C6.
- `Scenario.business_context` and `affected_products` are still free text with no consumer. C4's API decides whether they stay.

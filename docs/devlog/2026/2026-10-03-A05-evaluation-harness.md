# 2026-10-03 - A05 - Evaluation harness, gates, and a safety test that was not testing

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | A05 (`docs/backlog/issues/A05-evaluation-harness-per-language-golden-sets-metr.md`, #9), Wave 2 |
| PR / commit | not committed at time of writing |
| Units touched | `clarity.ai.evaluation` (new), `config/ai/gates.yaml` (new), `tests/evaluation`, `scripts/evaluate.py`, Makefile, CI |

## What changed

- **`clarity/ai/evaluation/`**: the harness. `datasets.py` (JSONL loaders for the
  intake and safety sets), `metrics.py` (macro F1, accuracy, pass-rate, all pure),
  `gates.py` (thresholds from config, verdicts, the release decision), `report.py`
  (the per-run artefact, JSON and Markdown).
- **`config/ai/gates.yaml`**: all five gates from plan 22 section 10, with their
  thresholds and their minimum dataset sizes. No threshold appears in code (I10),
  and a test reads the harness source to keep it that way.
- **`tests/evaluation/datasets/intake.jsonl`**: 20 labelled utterances per
  language across si, ta, en and si-en (Singlish). Synthetic, labelled as such.
- **`tests/evaluation/datasets/safety.jsonl`**: the injection corpus and the
  genuine complaints, moved out of `test_safety_set.py` so the suite and the
  nightly job read one file instead of keeping two copies.
- **`scripts/evaluate.py`** and `make eval`: runs the sets, applies the gates,
  writes the report, and **exits non-zero when any gate fails or could not be
  evaluated**.
- **`.github/workflows/nightly-eval.yml`**: the nightly job, with the report in
  the job summary and as an artefact. Nothing is `continue-on-error`.

## Why

Issue #9: there were no quality gates for language or answers. The safety set
from A03 existed but nothing scored it, and no dataset existed for anything else.

## The gap this found

**`test_the_whole_injection_set_executes_nothing` was not injecting anything.**

Its docstring said "the customer's words reach evaluation". They did not.
`open_case` takes no text, and the loop passed the injection to nothing:

```python
for _kind, _text in INJECTIONS:        # note the underscore
    case = clarity.cases.open_case(...)
    clarity.cases.evaluate(case.case_id)
```

So the test opened ten empty cases, evaluated them against system records, and
asserted the balance had not moved. It would have passed with the entire
injection corpus deleted. The one path customer text actually travels is
`handle_turn`, which the test never called.

Fixed: the loop now calls `handle_turn(text, case_id=...)`, so the text enters
the system before the world is checked. The architecture does hold with real
text going through (`executes_refused` is 1.000 over 10 injections), which is
the result the test was claiming all along without having shown it.

This is the same shape as the two gaps found in Wave 1: a suite that agreed with
itself (authorization parity comparing Python with Python) and a driver no test
called (OpenBao in compose, never exercised). All three reported green. It is
why this harness treats an unevaluable gate as a block.

## What the gates say today

`make eval` blocks, and these are the real numbers, not placeholders:

| Gate | Observed | Gate | Status |
|---|---|---|---|
| `intake.intent_f1 [si]` | 0.559 (n=20) | 0.90 | UNEVALUABLE, set below 300 |
| `intake.intent_f1 [ta]` | 0.520 (n=20) | 0.90 | UNEVALUABLE, set below 300 |
| `intake.intent_f1 [en]` | 0.688 (n=20) | 0.90 | UNEVALUABLE, set below 300 |
| `intake.intent_f1 [si-en]` | 0.305 (n=20) | 0.90 | UNEVALUABLE, set below 300 |
| `intake.slot_accuracy` | 1.000 (n=2 per language) | 0.90 | UNEVALUABLE, set below 300 |
| `safety.executes_refused` | 1.000 (n=10) | 1.00 | **PASS** |
| `flow.*` | not measured | - | UNEVALUABLE, no dataset (C01 #19, C02 #21) |
| `rag.*` | not measured | - | UNEVALUABLE, no dataset (K01 #31, K02 #32, K03 #33) |
| `language_review.mean_rating` | not measured | 4.0 | UNEVALUABLE, needs native speakers |

Two things worth reading off that table. The keyword intake is nowhere near the
0.90 gate in any language, and **worst in Singlish by a wide margin** (0.305),
which is the language a large share of HUTCH customers actually type. That is
C04 (#23). And `slot_accuracy` reads 1.000 on two examples per language, which
is exactly the vacuous number the size rule exists to refuse.

## Decisions made

1. **An unevaluable gate blocks the release.** Not a third state reviewers learn
   to ignore. A gate with no dataset, or whose dataset is below its declared
   minimum, blocks exactly as a regression does, with the reason attached.
2. **A gate is a threshold *and* a sample size.** `1.00` over four examples is
   not a pass. The metric is still computed and still reported, so the shortfall
   and the score are both visible rather than the gate silently disappearing.
3. **Flow, RAG and language review are declared, not omitted.** A gate absent
   from config is a gate that is silently satisfied. They are in `gates.yaml`,
   they block, and each carries the issue number that will bring its dataset.
4. **The intake set is not written against the matcher.** A test asserts the set
   contains utterances the current intake gets wrong. A set with no misses would
   have been written by reading the keyword patterns, which is self-agreement.
5. **The safety set keeps both halves.** `load_safety` refuses a one-sided set,
   because a guard measured only on injections scores perfectly by refusing
   every real complaint.
6. **Report time is injected, never `datetime.now()`** inside the harness (I11),
   so two runs over the same inputs produce identical reports.
7. **Language review stays human.** The harness reads a ratings file when one
   exists and reports UNEVALUABLE otherwise. Scoring its own fluency would be
   marking its own homework, which is why the `judge` role already ends in
   `local-unscored` (A01).

## Also found

- **Singlish has no detector output.** `detect_language` looks for Sinhala or
  Tamil script and falls back to `en`, so Singlish arrives as English. Intent F1
  for `si-en` is still measured because the dataset declares the language rather
  than asking the detector, but anything routing on detected language treats
  these customers as English speakers. Recorded as a test that fails when C04
  lands.
- **An attacker-supplied amount is extracted into the intake slots.** "refund me
  LKR 50000" puts `amount_lkr: 50000` in `intake.slots`. That is I2 working as
  designed (the figure narrows candidate events) and the amount never reaches a
  decision or the reply, but nothing asserted the second half. Now it does,
  across the whole corpus rather than on one example.

## Docs updated

- This devlog, `CHANGELOG.md`, `ARCHITECTURE.md`, `AGENTS.md` section 13
  (`make eval`), `plan.md` (#9 ticked).
- No `MODULE.md`: `clarity.ai` is L3, not a domain module.
- No `.env.example` change: the harness adds no variable (it sets
  `OTEL_EXPORTER=none` by default so span JSON does not bury the gate table).
- No `/v1` contract change, so the OpenAPI snapshot is untouched.

## Tests run

- `make check`: **1384 passed, 527 skipped** (1352 before A05, so +32).
- `make eval`: blocks with exit 1, naming every failing gate.
- Non-vacuity probe: changing `Verdict.blocks_release` so UNEVALUABLE stops
  blocking fails **6 tests**, including the subprocess test that asserts the
  nightly job exits non-zero. The rule is enforced by tests, not by comment.
- The injection-echo test is guarded by a second test asserting the corpus
  actually contains a figure, so it cannot pass by having nothing to check.

## Known gaps

- Three of five datasets have no subject built yet (flow, RAG, language review).
  Their gates block, which is the intended state, not a pass waiting to happen.
- The intake set needs to grow from 20 to 300 per language before its gate can
  score for real. `test_the_intake_gate_blocks_today_because_the_set_is_too_small`
  fails when it does, which is the signal to stop treating it as pending.
- `--mode live` records the mode in the report but no provider is configured in
  CI, so the nightly job runs recorded until one is.
- `Guard.check` is still not called by any request path. The MCP `search_knowledge`
  and `request_handoff` tools take free text and remain the place it belongs.

## Next step

Wave 3. C01 (#19) and C02 (#21) bring the flow dataset a subject; K01-K03
(#31-#33) bring RAG one. C04 (#23) is what moves the intake F1 gate, and the
Singlish number is the one to watch.

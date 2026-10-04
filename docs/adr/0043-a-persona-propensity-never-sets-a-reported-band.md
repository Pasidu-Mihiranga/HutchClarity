# 0043 - A persona propensity never sets a reported band

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Pasidu Mihiranga |
| Plan references | workstream C item C3 (F04, F11); enterprise-plan 02 §3.4, 08 §12.9; AGENTS.md I1 |

## Context

Foresight rehearses a change before it ships and reports a volume band per theme and segment. Until C3 there was one method: historic complaint rates per segment, scaled by the change. C3 adds two more, a round-based cohort simulation and an LLM-driven one, behind a `PersonaSimulator` port.

That raises a question I1 already answers for money and has to answer here too. I1 says rules decide and the LLM explains; it forbids an LLM supplying an amount or executing an action. A complaint propensity is not an amount, and foresight is advisory: nothing it produces can trigger a customer action. So it is tempting to treat a model's propensity as harmless.

It is not harmless. A band is read by a product manager deciding whether to delay a launch, write a migration card, or staff a queue. A number that decides a band is a decision-shaped number even when no money moves, and a model that supplied it would be deciding. The plan states the constraint and asks for it to be explicit: "under I1 a propensity that feeds a reported band is a decision-shaped number, so the statistical baseline stays the headline and the LLM driver is a comparison column. The port makes that structural rather than a convention."

The second force is comparability. Three methods are only worth comparing if they answer the same question in the same units. A driver that emitted bands would be comparing its own thresholds with another's, and a driver that emitted counts would be claiming a volume none of these methods can support.

## Decision

**The `PersonaSimulator` port returns propensities in [0, 1], never bands and never counts, and the statistical baseline is always the reported headline.**

Specifically:

1. A propensity is the share of **one segment** expected to complain about one theme in the month after the change. Per segment, not per subscriber base: how large a segment is belongs to the reporting step (`score_of`), not to the method.
2. Banding happens once, in the module, against the policy thresholds `foresight.band.high` and `foresight.band.medium`. No driver bands its own output.
3. `PersonaRehearsal` constructs its own `StatisticalBaseline`. It is not a constructor argument. The only injectable driver is named `comparison`, and its output reaches only `RehearsalReport.comparison`.
4. `RehearsalReport.predictions`, the bands anybody acts on, are built from the baseline alone.
5. Reporting a non-baseline driver's output as the primary band requires superseding this ADR and amending I1. It is not a configuration change and not a constructor argument.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Let the driver emit bands | Two drivers could then disagree because they banded differently rather than because they expect different things, and a driver could widen its own HIGH band. Banding is a policy question (I10), and policy thresholds belong to the module. |
| Let the driver emit complaint counts | A count is a claim about volume none of these methods supports. The deck's own footnote is the rule: scenarios, not certainties. It would also invite a reader to add counts across segments. |
| Inject the headline, document that it must be the baseline | Then I1 rests on nobody passing the other argument. The repository already has a case of a rule that held only because one of two drivers happened to be wrapped (B7, the OPA `granted` field); the lesson taken there was to make the enforcement structural. |
| Average the drivers into one band | An average of a measured-ish baseline and a model's guess is neither, and the resulting number would have no basis anyone could state. It also hides disagreement, which is the useful signal. |
| Keep one driver and skip the comparison | Plan 08 §12.9 asks for a baseline *alongside* a simulation, and the previous "swarm" compared the baseline against a hash of itself. A second genuine method is the point. |

## Consequences

**Positive**

- A model cannot move a band a product manager acts on, and a test asserts it: a comparison driver answering `1.0` for every pair leaves the reported bands identical.
- Drivers are comparable, because they answer one question in one unit.
- Where the two deterministic methods disagree is a usable signal: the baseline scales linearly with reach and severity, the round-based one compounds over rounds, so divergence points at the pairs where the segment assumptions carry the most weight.
- The reported `relative_score` is provably the baseline's propensity times the segment share, because the engine now reaches the baseline through the same port rather than keeping a second copy of the arithmetic.

**Negative**

- `PersonaRehearsal` cannot be used to evaluate a candidate replacement for the baseline on its own terms. That is deliberate; doing so is an experiment, not a report, and should not share a code path with the thing a product manager reads.
- The comparison column is absent, not zero, when a model does not answer. Consumers have to handle `None`, which is more work than a default, and is the point: a column of zeros reads as the finding that no segment will complain.

**What must now be true**

- `RehearsalReport.agreement_rate` is reported but every report says in its caveats that agreement proves nothing: both methods rest on the same segment catalogue and neither has been calibrated against a real launch.
- The LLM driver's parameters stay out of code and in `config/policy/foresight.yaml` like every other tunable (I10).
- No real cassette exists for the persona prompt yet (plan F1). Tests use a stub that says it is a stub; hand-writing a cassette would present an authored answer as a recorded one (I16).

## Compliance

- `tests/unit/test_foresight_personas.py::test_the_rehearsal_takes_no_headline_argument` inspects the constructor signature and fails if a `headline` or `baseline` parameter is added.
- `tests/unit/test_foresight_personas.py::test_a_confident_model_cannot_move_a_reported_band` wires a driver answering `1.0` everywhere and asserts the reported bands are unchanged.
- The parity suite asserts every driver returns values in [0, 1] and carries no `band`, `count` or `complaints` attribute.
- Review rule: a change that gives `PersonaRehearsal` a way to take the headline, or that bands inside a driver, supersedes this ADR.

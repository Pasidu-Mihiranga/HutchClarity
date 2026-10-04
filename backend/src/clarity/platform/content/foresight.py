"""Approved wording for foresight reports (C1/F03).

This sits beside :mod:`clarity.platform.content.templates` for the same reason
that file gives: it is **content**, no model produces it, and a module should
not have to import the AI package to get a sentence. Before C1 these strings
were literals inside ``modules/foresight/simulation.py`` and
``modules/foresight/backtest.py``, which made a CX wording change a code change.

**Why wording is here and numbers are in the policy store.** A mitigation line
and a caveat are prose a person approves once and reuses; a band threshold is a
value that is scoped, effective-dated and resolved per run (I10). Putting prose
in the policy store would make every wording fix a scoped artefact version, and
putting thresholds here would hard-code policy. The split follows what each one
actually is.

**Language.** English only, deliberately. Foresight is a staff and product tool
behind the console, not a customer surface, so none of this is covered by I15
and none of it reaches a subscriber. Console translation is a separate piece of
work (plan workstream E3); when it lands, these keys are what it translates, and
the structure here is already keyed rather than inlined so that is a change of
one dictionary rather than a hunt through the engine.

Every caveat in :data:`CAVEATS` exists because a reader could otherwise take the
report for something it is not. They are not boilerplate and should not be
trimmed for brevity.
"""

from __future__ import annotations

#: theme -> what to do about it before launch. Advisory, never an action: these
#: are read by a product manager, and nothing in the system executes them.
MITIGATIONS: dict[str, str] = {
    "pack sunset confusion": "Publish a migration card and a self-service flow before the change.",
    "wrong pack after migration": "Add a provisioning check and a one-tap correction.",
    "balance burn after pack ends": "Offer data-stop and a spend cap at pack end.",
    "unexpected charge amount": "Show the new price in the pack truth label before purchase.",
    "balance disappeared faster": "Send a proactive balance alert for affected segments.",
    "data stopped at cap": "State the cap and after-cap speed at purchase; alert at 80% and 95%.",
    "unlimited not unlimited": "Rename the offer and disclose the cap prominently.",
    "consent and subscription confusion": "Re-confirm consent and brief agents on the new policy.",
    "service unavailable": "Prepare an outage notice with an honest ETA.",
    "pack validity lost during outage": "Pre-approve a validity extension rule.",
}

#: Shown for a theme with no authored mitigation. It names a person rather than
#: inventing advice, which is the same instinct as I2: no evidence, no guess.
DEFAULT_MITIGATION = "Review with CX before launch."

#: Named caveats. The engine assembles the applicable ones; it never writes
#: prose of its own.
CAVEATS: dict[str, str] = {
    "scenarios_not_certainties": "Scenarios, not certainties (deck S11).",
    "bands_are_relative": (
        "Volume bands are relative within this run and are not complaint counts."
    ),
    "segments_are_assumptions": (
        "Segment shares and complaint rates are ASSUMPTIONS for the demo and have not "
        "been measured."
    ),
    "not_backtested": (
        "Not backtested against real launches, so not usable for a launch decision."
    ),
    "gate_not_reached": (
        "The backtest did not reach the plan 02 section 3.4 gate, so this report is "
        "still not usable for a launch decision."
    ),
    "advisory_only": ("Advisory only: a foresight report never authorises an automated action."),
}

#: Caveats a calibration report carries. Separate from :data:`CAVEATS` because a
#: backtest is read by a different person asking a different question: not "what
#: will this change do" but "is this engine worth listening to".
BACKTEST_CAVEATS: dict[str, str] = {
    "error_is_not_a_forecast": (
        "Results are scenarios, not certainties (deck S11). A calibration error does "
        "not turn a prediction into a forecast."
    ),
    "band_steps_not_complaints": (
        "The error is measured in band steps (LOW, MEDIUM, HIGH), not in complaints. "
        "Bands are relative within one run."
    ),
    "advisory_only": ("Advisory only: a calibration report never authorises an automated action."),
    "nothing_comparable": (
        "No observed theme matched a predicted one, so no calibration error could be measured."
    ),
    "under_predicted": (
        "The baseline under-predicted on average, which is the dangerous direction for "
        "CX capacity planning."
    ),
}


def synthetic_launches_caveat(synthetic: int, total: int) -> str:
    """Said whenever any launch in the backtest was authored rather than observed."""
    return (
        f"{synthetic} of {total} launches are SIMULATED, authored for the prototype. "
        "A synthetic backtest exercises the method and validates nothing."
    )


def below_gate_caveat(real: int, required: int) -> str:
    """Said when there are too few real launches for the plan's gate."""
    return (
        f"{real} real launches against the {required} the plan 02 section 3.4 gate "
        "requires, so this report does not establish calibration."
    )


def unpredicted_caveat(count: int) -> str:
    """Observed outcomes the engine never predicted: the dangerous direction."""
    return (
        f"Observed theme-segment outcomes never predicted at all: {count}. They are "
        "excluded from the error."
    )


def unobserved_caveat(count: int) -> str:
    """Predictions with no record either way. Absence is not a LOW observation."""
    return (
        f"Predicted theme-segment pairs with no recorded outcome: {count}. Absence of "
        "a record is not a LOW observation."
    )


#: Where a backtest's numbers came from.
BACKTEST_BASIS = (
    "Replay of recorded launch outcomes against the statistical baseline, "
    "aggregated per segment. No individual customer data was read."
)

#: Where a report's numbers came from. Stated on every report, because a reader
#: who does not know the basis cannot judge the output.
BASIS = (
    "Statistical baseline over aggregated segments, resolved from the policy "
    "store as of the scenario's effective date. No individual customer data was "
    "read."
)


def mitigation_for(theme: str) -> str:
    """The approved line for a theme, or the one that asks a person."""
    return MITIGATIONS.get(theme, DEFAULT_MITIGATION)


def borrowed_themes_caveat(change_type: str, lender: str) -> str:
    """Said when a change type has no themes of its own.

    Seven of the twelve change types borrow another's catalogue. Before C1 that
    happened silently inside a Python dict, so a reader of a ``new_pack``
    rehearsal had no way to know they were looking at themes authored for a pack
    retirement.
    """
    return (
        f"No themes are authored for {change_type}, so this report borrows the "
        f"{lender} catalogue. The themes were not written for this change."
    )


def no_themes_caveat(change_type: str) -> str:
    """Said when nothing is configured at all, instead of reporting silence.

    An empty report and a report about a change nobody has characterised look
    identical on screen, and only one of them means "we expect no complaints".
    """
    return (
        f"No theme catalogue is configured for {change_type} and it borrows none, "
        "so this run predicted nothing. That is a gap in the catalogue, not a "
        "finding that the change is safe."
    )


def band_thresholds_caveat() -> str:
    """Said when the MEDIUM threshold is not below the HIGH one."""
    return (
        "The configured MEDIUM band threshold is not below the HIGH one, so every "
        "pair at or above it reports HIGH. Check foresight.band.medium and "
        "foresight.band.high."
    )


__all__ = [
    "BACKTEST_BASIS",
    "BACKTEST_CAVEATS",
    "BASIS",
    "CAVEATS",
    "DEFAULT_MITIGATION",
    "MITIGATIONS",
    "band_thresholds_caveat",
    "below_gate_caveat",
    "borrowed_themes_caveat",
    "mitigation_for",
    "no_themes_caveat",
    "synthetic_launches_caveat",
    "unobserved_caveat",
    "unpredicted_caveat",
]

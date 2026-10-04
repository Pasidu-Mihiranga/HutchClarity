"""Foresight's parameters come from the policy store, not from code (C1/F03).

These tests exist because the interesting failure is silent. An engine that
falls back to a compiled-in segment mix when the catalogue is missing, or that
resolves "now" instead of the date the change lands, produces a report that
looks exactly like a correct one. So the assertions here are mostly about what
the engine *refuses* to do: no defaults, no shadowed values (D2), no quiet
parse, and no report that hides where its themes came from.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from clarity.modules.foresight.catalogue import (
    BAND_HIGH_KEY,
    BAND_MEDIUM_KEY,
    MIN_REAL_LAUNCHES_KEY,
    SEGMENTS_KEY,
    THEME_ALIASES_KEY,
    CatalogueInvalid,
    ChangeType,
    ForesightCatalogue,
    themes_key,
)
from clarity.modules.foresight.simulation import Foresight, Scenario, VolumeBand
from clarity.platform.config.artefacts import PolicyKey, PolicyValue, Tag
from clarity.platform.config.resolver import PolicyResolver
from tests.conftest import POLICY_DIR

_AS_OF = datetime(2027, 1, 1, tzinfo=UTC)
_EFFECTIVE = date(2027, 1, 1)


def shipped() -> ForesightCatalogue:
    """The catalogue the repository actually ships."""
    return ForesightCatalogue(PolicyResolver.from_directory(POLICY_DIR))


def catalogue_of(**keys: str) -> ForesightCatalogue:
    """A catalogue over exactly the keys a test names.

    Values are strings because that is what the YAML carries and what the
    resolver returns for a string key; a test that passed Decimals would be
    exercising a path the policy file cannot produce.
    """
    resolver = PolicyResolver()
    for name, value in keys.items():
        resolver.add(
            PolicyKey(
                key=name.replace("__", "."),
                kind="string",
                owner_role="product",
                tags={Tag.OPERATIONAL},
                values=[PolicyValue(value=value, version=1)],
            )
        )
    return ForesightCatalogue(resolver)


# --------------------------------------------------------------------------- #
# The values are policy, and nothing in code shadows them (I10, D2)
# --------------------------------------------------------------------------- #


def test_the_engine_has_no_constants_left_to_shadow_a_policy_value():
    """D2: a constant beside a policy key is the thing that gets read by mistake."""
    from clarity.modules.foresight import backtest, simulation

    assert not hasattr(simulation, "DEMO_SEGMENTS")
    assert not hasattr(simulation, "_THEMES")
    assert not hasattr(simulation, "_THEME_ALIASES")
    assert not hasattr(simulation, "_MITIGATIONS")
    assert not hasattr(backtest, "MIN_REAL_LAUNCHES")
    assert not hasattr(Foresight, "_HIGH")
    assert not hasattr(Foresight, "_MEDIUM")


def test_changing_the_band_threshold_changes_the_report():
    """The proof that the threshold is read rather than compiled in."""
    themes = "one theme|1.0|data_intensity"
    segments = "everyone|1.0|1.0|1.0|1.0"
    loud = catalogue_of(
        foresight__segments=segments,
        **{"foresight__themes__outage": themes},
        foresight__band__high="0.5",
        foresight__band__medium="0.1",
    )
    quiet = catalogue_of(
        foresight__segments=segments,
        **{"foresight__themes__outage": themes},
        foresight__band__high="99",
        foresight__band__medium="98",
    )
    rehearsed = Scenario(name="probe", change_type=ChangeType.OUTAGE, effective_date=_EFFECTIVE)

    assert Foresight(loud).run(rehearsed).predictions[0].band is VolumeBand.HIGH
    assert Foresight(quiet).run(rehearsed).predictions[0].band is VolumeBand.LOW


def test_a_scenario_resolves_policy_as_of_its_effective_date_not_now():
    """A rehearsal of an October change uses October's segments.

    This is the whole reason `effective_date` became required and typed. The
    resolver is given two windows for the segment catalogue; the engine must
    pick by the date the change lands, not by the clock it is run on.
    """
    resolver = PolicyResolver()
    resolver.add(
        PolicyKey(
            key=SEGMENTS_KEY,
            kind="string",
            owner_role="product",
            tags={Tag.OPERATIONAL},
            values=[
                PolicyValue(
                    value="before|1.0|1.0|1.0|1.0",
                    effective_to=datetime(2027, 6, 1, tzinfo=UTC),
                    version=1,
                ),
                PolicyValue(
                    value="after|1.0|1.0|1.0|1.0",
                    effective_from=datetime(2027, 6, 1, tzinfo=UTC),
                    version=2,
                ),
            ],
        )
    )
    catalogue = ForesightCatalogue(resolver)

    assert [s.name for s in catalogue.segments(datetime(2027, 1, 1, tzinfo=UTC))] == ["before"]
    assert [s.name for s in catalogue.segments(datetime(2027, 10, 1, tzinfo=UTC))] == ["after"]


def test_the_calibration_gate_is_resolved_rather_than_compiled_in():
    assert shipped().min_real_launches(_AS_OF) == 3


def test_lowering_the_calibration_gate_below_three_is_refused_by_its_guardrail():
    """The gate is the one number a synthetic backtest would want moved."""
    key = PolicyResolver.from_directory(POLICY_DIR).key(MIN_REAL_LAUNCHES_KEY)

    assert key.guardrail is not None
    assert key.guardrail.min == Decimal("3")
    assert not key.guardrail.permits(Decimal("2"))


def test_the_calibration_gate_needs_a_second_approver_to_change():
    """Tagged regulatory, so `class_for` derives C4 (plan 20)."""
    key = PolicyResolver.from_directory(POLICY_DIR).key(MIN_REAL_LAUNCHES_KEY)

    assert key.change_class.needs_second_approver


# --------------------------------------------------------------------------- #
# A malformed catalogue fails loudly
# --------------------------------------------------------------------------- #


def test_a_segment_row_with_the_wrong_field_count_is_refused():
    catalogue = catalogue_of(foresight__segments="students|0.28|0.09")

    with pytest.raises(CatalogueInvalid, match="expected 5"):
        catalogue.segments(_AS_OF)


def test_an_empty_segment_catalogue_is_refused_rather_than_run_on_nothing():
    """A run over no segments predicts nothing, which reads as "no risk"."""
    catalogue = catalogue_of(foresight__segments="  ")

    with pytest.raises(CatalogueInvalid, match="no segments"):
        catalogue.segments(_AS_OF)


def test_a_segment_share_outside_zero_to_one_is_refused_at_parse_time():
    catalogue = catalogue_of(foresight__segments="impossible|1.5|0.1|1.0|1.0")

    with pytest.raises(CatalogueInvalid, match="fraction"):
        catalogue.segments(_AS_OF)


def test_an_unknown_theme_driver_is_refused_rather_than_silently_scaling_by_one():
    """`getattr` on an unchecked string is how a typo becomes a 1.0 multiplier."""
    catalogue = catalogue_of(**{"foresight__themes__outage": "theme|1.0|made_up"})

    with pytest.raises(CatalogueInvalid, match="not a known driver"):
        catalogue.themes(ChangeType.OUTAGE, _AS_OF)


def test_a_driver_naming_another_attribute_of_the_segment_is_refused():
    """The driver list is an allowlist, not a convention."""
    catalogue = catalogue_of(**{"foresight__themes__outage": "theme|1.0|name"})

    with pytest.raises(CatalogueInvalid, match="not a known driver"):
        catalogue.themes(ChangeType.OUTAGE, _AS_OF)


def test_an_unknown_change_type_in_the_alias_catalogue_is_refused():
    catalogue = catalogue_of(foresight__theme_aliases="not_a_change_type=outage")

    with pytest.raises(CatalogueInvalid, match="not a known change type"):
        catalogue.themes(ChangeType.NEW_PACK, _AS_OF)


def test_an_alias_pointing_at_a_type_with_no_themes_is_refused():
    """Borrowing from an empty shelf is a configuration error, not an empty run."""
    catalogue = catalogue_of(foresight__theme_aliases="new_pack=outage")

    with pytest.raises(CatalogueInvalid, match="no theme catalogue"):
        catalogue.themes(ChangeType.NEW_PACK, _AS_OF)


def test_a_fractional_calibration_gate_is_refused():
    catalogue = catalogue_of(foresight__calibration__min_real_launches="2.5")

    with pytest.raises(CatalogueInvalid, match="whole number"):
        catalogue.min_real_launches(_AS_OF)


# --------------------------------------------------------------------------- #
# Borrowed themes are declared, not silent
# --------------------------------------------------------------------------- #


def test_a_change_type_with_its_own_themes_borrows_nothing():
    assert shipped().themes(ChangeType.OUTAGE, _AS_OF).borrowed_from is None


def test_a_borrowing_change_type_names_its_lender():
    """Seven of twelve types borrow. Before C1 that was a silent Python dict."""
    borrowed = shipped().themes(ChangeType.NEW_PACK, _AS_OF)

    assert borrowed.borrowed_from is ChangeType.PACK_RETIRED
    assert borrowed.themes


def test_a_report_on_borrowed_themes_says_so_in_its_caveats():
    report = Foresight(shipped()).run(
        Scenario(name="New pack", change_type=ChangeType.NEW_PACK, effective_date=_EFFECTIVE)
    )

    assert any("borrows" in c and "pack_retired" in c for c in report.caveats)


def test_borrowing_follows_one_level_only():
    """A chain of aliases hides which catalogue a report actually used."""
    catalogue = catalogue_of(
        foresight__theme_aliases="new_pack=promotion_end;promotion_end=outage",
        **{"foresight__themes__outage": "theme|1.0|data_intensity"},
    )

    with pytest.raises(CatalogueInvalid, match="no theme catalogue"):
        catalogue.themes(ChangeType.NEW_PACK, _AS_OF)


def test_a_change_type_nobody_characterised_says_so_rather_than_predicting_nothing():
    """An empty report and "we expect no complaints" look identical otherwise."""
    report = Foresight(
        catalogue_of(
            foresight__segments="everyone|1.0|1.0|1.0|1.0",
            foresight__band__high="0.5",
            foresight__band__medium="0.1",
        )
    ).run(
        Scenario(
            name="uncharacterised",
            change_type=ChangeType.VAS_CONSENT_CHANGE,
            effective_date=_EFFECTIVE,
        )
    )

    assert report.predictions == []
    assert any("not a finding that the change is safe" in c for c in report.caveats)


def test_bands_that_are_not_ordered_are_called_out():
    report = Foresight(
        catalogue_of(
            foresight__segments="everyone|1.0|1.0|1.0|1.0",
            **{"foresight__themes__outage": "theme|1.0|data_intensity"},
            foresight__band__high="0.1",
            foresight__band__medium="0.5",
        )
    ).run(Scenario(name="probe", change_type=ChangeType.OUTAGE, effective_date=_EFFECTIVE))

    assert any("MEDIUM band threshold is not below" in c for c in report.caveats)


# --------------------------------------------------------------------------- #
# A scenario is a value, so a run can cite it
# --------------------------------------------------------------------------- #


def test_a_scenario_id_is_stable_across_reads():
    """It was a `@property` calling `new_id`, so every read returned a new id.

    Nothing could store, compare or cite a scenario, which is also why nothing
    did. C2's persistence rests on this being a field.
    """
    rehearsed = Scenario(name="probe", change_type=ChangeType.OUTAGE, effective_date=_EFFECTIVE)

    assert rehearsed.scenario_id == rehearsed.scenario_id
    assert rehearsed.scenario_id.startswith("SIM")


def test_two_scenarios_get_different_ids():
    first = Scenario(name="a", change_type=ChangeType.OUTAGE, effective_date=_EFFECTIVE)
    second = Scenario(name="b", change_type=ChangeType.OUTAGE, effective_date=_EFFECTIVE)

    assert first.scenario_id != second.scenario_id


def test_a_scenario_cannot_be_changed_after_a_run_cited_it():
    rehearsed = Scenario(name="probe", change_type=ChangeType.OUTAGE, effective_date=_EFFECTIVE)

    with pytest.raises(FrozenInstanceError):
        rehearsed.name = "something else"  # type: ignore[misc]


def test_an_effective_date_is_required():
    """It was an optional free-text string that nothing read."""
    with pytest.raises(TypeError, match="effective_date"):
        Scenario(name="probe", change_type=ChangeType.OUTAGE)  # type: ignore[call-arg]


def test_a_report_carries_the_scenario_and_the_date_it_was_resolved_at():
    rehearsed = Scenario(name="probe", change_type=ChangeType.OUTAGE, effective_date=_EFFECTIVE)

    report = Foresight(shipped()).run(rehearsed)

    assert report.scenario_id == rehearsed.scenario_id
    assert report.effective_date == _EFFECTIVE


def test_a_report_timestamps_itself_from_the_injected_clock():
    """I11: a replay must agree with the trail it is read beside."""
    frozen = datetime(2026, 2, 3, 4, 5, tzinfo=UTC)

    report = Foresight(shipped(), clock=lambda: frozen).run(
        Scenario(name="probe", change_type=ChangeType.OUTAGE, effective_date=_EFFECTIVE)
    )

    assert report.generated_at == frozen


# --------------------------------------------------------------------------- #
# The shipped catalogue is complete
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("change_type", list(ChangeType))
def test_every_change_type_resolves_to_a_theme_catalogue(change_type: ChangeType):
    """Twelve types, five catalogues, seven aliases. None may fall through."""
    assert shipped().themes(change_type, _AS_OF).themes


def test_the_shipped_keys_are_the_ones_the_module_asks_for():
    resolver = PolicyResolver.from_directory(POLICY_DIR)

    for key in (SEGMENTS_KEY, THEME_ALIASES_KEY, BAND_HIGH_KEY, BAND_MEDIUM_KEY):
        assert resolver.key(key)
    for change_type in (
        ChangeType.PACK_RETIRED,
        ChangeType.PRICE_INCREASE,
        ChangeType.FUP_TIGHTENED,
        ChangeType.POLICY_CHANGE,
        ChangeType.OUTAGE,
    ):
        assert resolver.key(themes_key(change_type))

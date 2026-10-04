"""Foresight's parameters, read from the policy store (C1/F03).

Before C1 every number in this module was a Python constant: the segment mix,
the theme weights, which change types borrowed another's themes, the band
thresholds, and the calibration gate. A product manager could not change any of
them without a release, which is exactly what I10 forbids.

They are policy artefacts now, and this file is the one place that turns the
resolver's answers into typed values. Two things follow from that and are worth
stating, because both are easy to get wrong later:

1. **Everything resolves `as_of` a moment**, and for a scenario that moment is
   the date the change takes effect, never "now". A rehearsal of an October
   change must use the segment mix that applies in October, including a value
   that was approved today with an effective window that starts then.
2. **A malformed catalogue fails loudly here**, at parse time, rather than
   producing a plausible-looking report from half a row. A silent default is
   how a rehearsal quietly stops describing the business it is rehearsing.

The catalogues are CSV strings because the resolver returns money, number, bool
and string and nothing else (``platform/config/resolver.py::_coerce``);
``config/policy/proactive.yaml`` takes the same escape hatch. Rows split on
``;`` and fields on ``|``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from clarity.platform.config.resolver import PolicyResolver, UnknownPolicyKey

_ROW = ";"
_FIELD = "|"

#: Policy key names, in one place so a typo is a NameError rather than an
#: `UnknownPolicyKey` raised from somewhere in the middle of a run.
SEGMENTS_KEY = "foresight.segments"
THEME_ALIASES_KEY = "foresight.theme_aliases"
BAND_HIGH_KEY = "foresight.band.high"
BAND_MEDIUM_KEY = "foresight.band.medium"
MIN_REAL_LAUNCHES_KEY = "foresight.calibration.min_real_launches"
RADAR_WINDOW_KEY = "foresight.radar.window_minutes"
RADAR_BASELINE_WINDOWS_KEY = "foresight.radar.baseline_windows"
RADAR_THRESHOLD_KEY = "foresight.radar.threshold_multiple"
RADAR_MIN_OBSERVATIONS_KEY = "foresight.radar.min_observations"


def themes_key(change_type: ChangeType) -> str:
    return f"foresight.themes.{change_type.value}"


class ChangeType(StrEnum):
    PACK_RETIRED = "pack_retired"
    PRICE_INCREASE = "price_increase"
    FUP_TIGHTENED = "fup_tightened"
    POLICY_CHANGE = "policy_change"
    OUTAGE = "outage"
    PACK_MIGRATION = "pack_migration"
    FUP_DISCLOSURE_CHANGE = "fup_disclosure_change"
    VAS_CONSENT_CHANGE = "vas_consent_change"
    SOCIAL_PACK_SCOPE_CHANGE = "social_pack_scope_change"
    PAYG_PRICE_CHANGE = "payg_price_change"
    NEW_PACK = "new_pack"
    PROMOTION_END = "promotion_end"


class CatalogueInvalid(ValueError):
    """A policy catalogue could not be read.

    Raised rather than defaulted: a foresight run on a half-parsed segment list
    reports numbers nobody authored, and it reports them in the same shape as a
    correct run.
    """


#: Segment attributes a theme weight may be scaled by. Checked at parse time so
#: a typo in the catalogue cannot reach ``getattr`` and silently scale by 1.0,
#: and so no policy string can name an arbitrary attribute of the dataclass.
DRIVERS: frozenset[str] = frozenset({"price_sensitivity", "data_intensity"})


@dataclass(frozen=True)
class Segment:
    """An aggregated persona. No individual data, ever (deck S8)."""

    name: str
    share_of_base: Decimal
    """Fraction of the subscriber base, 0-1."""
    monthly_complaint_rate: Decimal
    """Historic complaints per subscriber per month, from aggregates."""
    price_sensitivity: Decimal = Decimal("1.0")
    data_intensity: Decimal = Decimal("1.0")

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.share_of_base <= Decimal("1"):
            raise ValueError("share_of_base must be a fraction between 0 and 1")
        if self.monthly_complaint_rate < 0:
            raise ValueError("monthly_complaint_rate cannot be negative")


@dataclass(frozen=True)
class ThemeWeight:
    """One theme a change type tends to produce, and how strongly."""

    theme: str
    weight: Decimal
    driver: str
    """The segment attribute the weight is scaled by. One of :data:`DRIVERS`."""

    def sensitivity_of(self, segment: Segment) -> Decimal:
        return Decimal(str(getattr(segment, self.driver)))


@dataclass(frozen=True)
class ThemeCatalogue:
    """The themes for one change type, and whose catalogue they are."""

    themes: tuple[ThemeWeight, ...]
    borrowed_from: ChangeType | None = None
    """Set when this change type has no catalogue and uses another's."""


@dataclass(frozen=True)
class RadarSettings:
    """The early-warning radar's parameters (C5/F08).

    Here beside the keys they are read from, so the detector has no constant to
    shadow one with (D2).
    """

    window: timedelta
    baseline_windows: int
    threshold_multiple: Decimal
    min_observations: int


@dataclass(frozen=True)
class Bands:
    """Score thresholds for the three volume bands."""

    high: Decimal
    medium: Decimal

    @property
    def is_ordered(self) -> bool:
        """False when MEDIUM is not below HIGH, which collapses the bands."""
        return self.medium < self.high


class ForesightCatalogue:
    """Reads foresight's parameters from the policy store.

    One instance per container, resolving per call: the resolver is the thing
    that knows about scopes and effective windows, and caching its answers here
    would mean a run could use a value that had been superseded.
    """

    def __init__(self, policies: PolicyResolver) -> None:
        self._policies = policies

    # -- catalogues -------------------------------------------------------- #

    def segments(self, as_of: datetime) -> tuple[Segment, ...]:
        """The segment mix that applies at ``as_of``."""
        rows = _rows(self._text(SEGMENTS_KEY, as_of), SEGMENTS_KEY)
        if not rows:
            raise CatalogueInvalid(f"{SEGMENTS_KEY}: no segments configured")
        return tuple(_segment(row, index) for index, row in enumerate(rows))

    def themes(self, change_type: ChangeType, as_of: datetime) -> ThemeCatalogue:
        """The themes for a change type, following one level of borrowing.

        One level only, and deliberately: a chain of aliases is a way to end up
        reading a catalogue three hops from the change you asked about, and
        nobody reviewing the policy file would see it.
        """
        own = self._themes_for(change_type, as_of)
        if own is not None:
            return ThemeCatalogue(own)

        lender = self._aliases(as_of).get(change_type)
        if lender is None:
            return ThemeCatalogue(())
        borrowed = self._themes_for(lender, as_of)
        if borrowed is None:
            raise CatalogueInvalid(
                f"{THEME_ALIASES_KEY}: {change_type.value} borrows from "
                f"{lender.value}, which has no theme catalogue of its own"
            )
        return ThemeCatalogue(borrowed, borrowed_from=lender)

    def bands(self, as_of: datetime) -> Bands:
        return Bands(
            high=_decimal(self._policies.resolve(BAND_HIGH_KEY, as_of=as_of), BAND_HIGH_KEY),
            medium=_decimal(self._policies.resolve(BAND_MEDIUM_KEY, as_of=as_of), BAND_MEDIUM_KEY),
        )

    def radar(self, as_of: datetime) -> RadarSettings:
        """The radar's parameters at ``as_of``."""
        return RadarSettings(
            window=timedelta(minutes=self._whole(RADAR_WINDOW_KEY, as_of)),
            baseline_windows=self._whole(RADAR_BASELINE_WINDOWS_KEY, as_of),
            threshold_multiple=_decimal(
                self._policies.resolve(RADAR_THRESHOLD_KEY, as_of=as_of), RADAR_THRESHOLD_KEY
            ),
            min_observations=self._whole(RADAR_MIN_OBSERVATIONS_KEY, as_of),
        )

    def _whole(self, key: str, as_of: datetime) -> int:
        value = _decimal(self._policies.resolve(key, as_of=as_of), key)
        if value != value.to_integral_value() or value <= 0:
            raise CatalogueInvalid(f"{key}: {value} is not a positive whole number")
        return int(value)

    def min_real_launches(self, as_of: datetime) -> int:
        """Plan 02 section 3.4's gate, resolved rather than compiled in."""
        value = _decimal(
            self._policies.resolve(MIN_REAL_LAUNCHES_KEY, as_of=as_of), MIN_REAL_LAUNCHES_KEY
        )
        if value != value.to_integral_value():
            raise CatalogueInvalid(f"{MIN_REAL_LAUNCHES_KEY}: {value} is not a whole number")
        return int(value)

    # -- internals --------------------------------------------------------- #

    def _themes_for(
        self, change_type: ChangeType, as_of: datetime
    ) -> tuple[ThemeWeight, ...] | None:
        key = themes_key(change_type)
        try:
            raw = self._policies.resolve(key, as_of=as_of)
        except UnknownPolicyKey:
            return None
        rows = _rows(str(raw), key)
        return tuple(_theme(row, key) for row in rows) if rows else None

    def _aliases(self, as_of: datetime) -> dict[ChangeType, ChangeType]:
        try:
            raw = self._policies.resolve(THEME_ALIASES_KEY, as_of=as_of)
        except UnknownPolicyKey:
            return {}
        aliases: dict[ChangeType, ChangeType] = {}
        for row in _rows(str(raw), THEME_ALIASES_KEY):
            borrower, _, lender = row.partition("=")
            if not lender:
                raise CatalogueInvalid(
                    f"{THEME_ALIASES_KEY}: {row!r} is not a change_type=lender pair"
                )
            aliases[_change_type(borrower, THEME_ALIASES_KEY)] = _change_type(
                lender, THEME_ALIASES_KEY
            )
        return aliases

    def _text(self, key: str, as_of: datetime) -> str:
        return str(self._policies.resolve(key, as_of=as_of))


# -- parsing ---------------------------------------------------------------- #


def _rows(raw: str, key: str) -> list[str]:
    return [row.strip() for row in raw.split(_ROW) if row.strip()]


def _segment(row: str, index: int) -> Segment:
    fields = [field.strip() for field in row.split(_FIELD)]
    if len(fields) != 5:
        raise CatalogueInvalid(
            f"{SEGMENTS_KEY}: row {index} has {len(fields)} fields, expected 5 "
            "(name|share|rate|price_sensitivity|data_intensity)"
        )
    name, share, rate, price, data = fields
    if not name:
        raise CatalogueInvalid(f"{SEGMENTS_KEY}: row {index} has an empty name")
    try:
        return Segment(
            name=name,
            share_of_base=_decimal(share, SEGMENTS_KEY),
            monthly_complaint_rate=_decimal(rate, SEGMENTS_KEY),
            price_sensitivity=_decimal(price, SEGMENTS_KEY),
            data_intensity=_decimal(data, SEGMENTS_KEY),
        )
    except ValueError as error:  # Segment's own invariants
        raise CatalogueInvalid(f"{SEGMENTS_KEY}: row {index}: {error}") from error


def _theme(row: str, key: str) -> ThemeWeight:
    fields = [field.strip() for field in row.split(_FIELD)]
    if len(fields) != 3:
        raise CatalogueInvalid(
            f"{key}: {row!r} has {len(fields)} fields, expected 3 (theme|weight|driver)"
        )
    theme, weight, driver = fields
    if not theme:
        raise CatalogueInvalid(f"{key}: a theme name cannot be empty")
    if driver not in DRIVERS:
        raise CatalogueInvalid(
            f"{key}: {driver!r} is not a known driver; expected one of {sorted(DRIVERS)}"
        )
    return ThemeWeight(theme=theme, weight=_decimal(weight, key), driver=driver)


def _change_type(raw: str, key: str) -> ChangeType:
    try:
        return ChangeType(raw.strip())
    except ValueError as error:
        raise CatalogueInvalid(f"{key}: {raw!r} is not a known change type") from error


def _decimal(raw: object, key: str) -> Decimal:
    try:
        return Decimal(str(raw))
    except InvalidOperation as error:
        raise CatalogueInvalid(f"{key}: {raw!r} is not a number") from error


__all__ = [
    "BAND_HIGH_KEY",
    "BAND_MEDIUM_KEY",
    "DRIVERS",
    "MIN_REAL_LAUNCHES_KEY",
    "RADAR_BASELINE_WINDOWS_KEY",
    "RADAR_MIN_OBSERVATIONS_KEY",
    "RADAR_THRESHOLD_KEY",
    "RADAR_WINDOW_KEY",
    "SEGMENTS_KEY",
    "THEME_ALIASES_KEY",
    "Bands",
    "CatalogueInvalid",
    "ChangeType",
    "ForesightCatalogue",
    "RadarSettings",
    "Segment",
    "ThemeCatalogue",
    "ThemeWeight",
    "themes_key",
]

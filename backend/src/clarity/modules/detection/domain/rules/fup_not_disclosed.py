"""FUP cap applied but not disclosed at purchase (catalogue version)."""

from __future__ import annotations

from typing import Any

from clarity.modules.detection.domain.models import Detection
from clarity.modules.detection.domain.rules._util import events


class FupNotDisclosedDetector:
    rule_id = "FUP_NOT_DISCLOSED"
    version = "1"

    def evaluate(self, timeline: dict[str, Any]) -> Detection | None:
        usage = events(timeline, "usage")
        packs = events(timeline, "packs")

        fup_hits = [
            u
            for u in usage
            if u.get("event") in {"fup_cap", "fup_reached", "fup_throttle"}
            or u.get("fup_applied") is True
        ]
        if not fup_hits:
            return None

        for pack in packs:
            disclosed = pack.get("fup_disclosed")
            catalogue_shows_fup = pack.get("catalogue_fup") is not None or pack.get(
                "fup_in_catalogue"
            )
            if disclosed is False or (disclosed is None and catalogue_shows_fup is False):
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.87,
                    evidence=[
                        {"kind": "pack", "ref": pack.get("id") or pack},
                        {"kind": "usage", "ref": fup_hits[0].get("id") or fup_hits[0]},
                    ],
                )
            if disclosed is None and not catalogue_shows_fup and pack.get("labelled_unlimited"):
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.86,
                    evidence=[
                        {"kind": "pack", "ref": pack.get("id") or pack},
                        {"kind": "usage", "ref": fup_hits[0].get("id") or fup_hits[0]},
                        {"kind": "note", "detail": "labelled_unlimited_without_fup"},
                    ],
                )

        # No pack metadata but FUP applied with explicit undisclosed flag on usage.
        for hit in fup_hits:
            if hit.get("disclosed") is False:
                return Detection(
                    rule_id=self.rule_id,
                    version=self.version,
                    confidence=0.85,
                    evidence=[{"kind": "usage", "ref": hit.get("id") or hit}],
                )
        return None


detect = FupNotDisclosedDetector()

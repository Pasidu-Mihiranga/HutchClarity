"""Customer safeguards: spend cap, quiet hours, language, auto-refund."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from clarity.kernel.common import Language, money


@dataclass(slots=True)
class QuietHours:
    """Local quiet window (hours 0-23). Inclusive start, exclusive end."""

    start_hour: int = 21
    end_hour: int = 7
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_hour": self.start_hour,
            "end_hour": self.end_hour,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> QuietHours:
        if not raw:
            return cls()
        return cls(
            start_hour=int(raw.get("start_hour", 21)),
            end_hour=int(raw.get("end_hour", 7)),
            enabled=bool(raw.get("enabled", True)),
        )


@dataclass(slots=True)
class Safeguards:
    """Per-subscriber preference and money-safety controls."""

    subscriber_ref: str
    spend_cap_lkr: Decimal = field(default_factory=lambda: Decimal("0.00"))
    quiet_hours: QuietHours = field(default_factory=QuietHours)
    language: Language = Language.EN
    allow_auto_refund: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "subscriber_ref": self.subscriber_ref,
            "spend_cap_lkr": f"{self.spend_cap_lkr:.2f}",
            "quiet_hours": self.quiet_hours.to_dict(),
            "language": self.language.value,
            "allow_auto_refund": self.allow_auto_refund,
        }

    @classmethod
    def defaults(cls, subscriber_ref: str) -> Safeguards:
        return cls(subscriber_ref=subscriber_ref)

    @classmethod
    def from_dict(cls, subscriber_ref: str, raw: dict[str, Any]) -> Safeguards:
        language = raw.get("language", Language.EN.value)
        lang = language if isinstance(language, Language) else Language(str(language))
        cap = raw.get("spend_cap_lkr", "0.00")
        return cls(
            subscriber_ref=subscriber_ref,
            spend_cap_lkr=money(cap),
            quiet_hours=QuietHours.from_dict(raw.get("quiet_hours")),
            language=lang,
            allow_auto_refund=bool(raw.get("allow_auto_refund", True)),
        )

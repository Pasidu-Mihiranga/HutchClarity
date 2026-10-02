"""Versioned CX template registry and feature flags."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clarity.kernel.common import utc_now


@dataclass(slots=True)
class TemplateVersion:
    version: int
    body: str
    language: str = "en"
    channel: str = "app"
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    created_by: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "body": self.body,
            "language": self.language,
            "channel": self.channel,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


@dataclass
class TemplateRecord:
    id: str
    name: str
    versions: list[TemplateVersion] = field(default_factory=list)

    @property
    def current(self) -> TemplateVersion | None:
        return self.versions[-1] if self.versions else None

    def to_dict(self) -> dict[str, Any]:
        current = self.current
        return {
            "id": self.id,
            "name": self.name,
            "version": current.version if current else 0,
            "body": current.body if current else "",
            "language": current.language if current else "en",
            "channel": current.channel if current else "app",
            "versions": [v.to_dict() for v in self.versions],
        }


DEFAULT_TEMPLATES: dict[str, tuple[str, str]] = {
    "fup_80_notice": ("FUP 80% notice", "You have used 80% of your fair-use data."),
    "fup_95_notice": ("FUP 95% notice", "You have used 95% of your fair-use data."),
    "vas_renewal": ("VAS renewal", "Your subscription renews soon. Manage it in the app."),
    "outage_heads_up": ("Outage heads-up", "Network issue in your area. ETA {{eta}}."),
    "pack_end_choice": ("Pack end choice", "Your pack ends soon. Choose renew, change, or stop."),
}


class TemplateRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, TemplateRecord] = {}
        self._flags: dict[str, bool] = {
            "proactive_messages": True,
            "auto_fix": True,
            "llm_answers": False,
            "bulk_fix": True,
        }
        self._seed()

    def _seed(self) -> None:
        for tid, (name, body) in DEFAULT_TEMPLATES.items():
            record = TemplateRecord(id=tid, name=name)
            record.versions.append(TemplateVersion(version=1, body=body))
            self._templates[tid] = record

    def get(self, template_id: str) -> TemplateRecord | None:
        return self._templates.get(template_id)

    def put(
        self,
        template_id: str,
        *,
        body: str,
        name: str | None = None,
        language: str = "en",
        channel: str = "app",
        created_by: str = "admin",
    ) -> TemplateRecord:
        record = self._templates.get(template_id)
        if record is None:
            record = TemplateRecord(id=template_id, name=name or template_id)
            self._templates[template_id] = record
        elif name:
            record.name = name
        next_ver = (record.current.version + 1) if record.current else 1
        record.versions.append(
            TemplateVersion(
                version=next_ver,
                body=body,
                language=language,
                channel=channel,
                created_by=created_by,
            )
        )
        return record

    def flags(self) -> dict[str, bool]:
        return dict(self._flags)

    def set_flag(self, key: str, value: bool) -> dict[str, bool]:
        self._flags[key] = value
        return self.flags()

    def clear(self) -> None:
        self._templates.clear()
        self._flags.clear()
        self._seed()

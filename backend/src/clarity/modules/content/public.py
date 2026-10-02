"""Public facade for the content module."""

from __future__ import annotations

from typing import Any

from clarity.modules.content.domain.registry import TemplateRegistry

_registry = TemplateRegistry()


def reset_content() -> None:
    _registry.clear()


def get_template(template_id: str) -> dict[str, Any]:
    record = _registry.get(template_id)
    if record is None:
        raise KeyError(template_id)
    return record.to_dict()


def put_template(
    template_id: str,
    *,
    body: str,
    name: str | None = None,
    language: str = "en",
    channel: str = "app",
    created_by: str = "admin",
) -> dict[str, Any]:
    return _registry.put(
        template_id,
        body=body,
        name=name,
        language=language,
        channel=channel,
        created_by=created_by,
    ).to_dict()


def get_flags() -> dict[str, bool]:
    return _registry.flags()


__all__ = ["get_flags", "get_template", "put_template", "reset_content"]

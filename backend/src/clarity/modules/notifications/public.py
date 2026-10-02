"""Public facade for the notifications module."""

from __future__ import annotations

from typing import Any

from clarity.modules.notifications.domain.service import (
    TEMPLATES,
    DeliveryStatus,
    NotificationRecord,
    NotificationService,
    Preferences,
    get_notifications,
    render_template,
)


def send_notification(**kwargs: Any) -> NotificationRecord:
    return get_notifications().send(**kwargs)


def get_status(notification_id: str) -> NotificationRecord | None:
    return get_notifications().status(notification_id)


def list_templates() -> list[str]:
    return sorted(TEMPLATES)


__all__ = [
    "TEMPLATES",
    "DeliveryStatus",
    "NotificationRecord",
    "NotificationService",
    "Preferences",
    "get_notifications",
    "get_status",
    "list_templates",
    "render_template",
    "send_notification",
]

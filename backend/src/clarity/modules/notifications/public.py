"""Public surface of the notifications module."""

from __future__ import annotations

from clarity.modules.notifications.service import (
    CONSUMED_EVENTS,
    NOTIFICATIONS,
    PREFERENCES,
    DeliveryStatus,
    DispatchFailed,
    MemoryNotificationDispatcher,
    NotificationRecord,
    NotificationRefused,
    NotificationRequest,
    NotificationService,
    Purpose,
    RecipientPreference,
)

__all__ = [
    "CONSUMED_EVENTS",
    "NOTIFICATIONS",
    "PREFERENCES",
    "DeliveryStatus",
    "DispatchFailed",
    "MemoryNotificationDispatcher",
    "NotificationRecord",
    "NotificationRefused",
    "NotificationRequest",
    "NotificationService",
    "Purpose",
    "RecipientPreference",
]

"""Template-only dispatch, preferences, quiet hours, delivery status."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from clarity.kernel.principal import Permission
from clarity.modules.notifications.domain.service import NotificationService, Preferences
from clarity.modules.notifications.public import get_notifications, get_status, send_notification
from clarity.platform.app.module import AppBuilder, ConfigKey


class SendBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    params: dict[str, str] = Field(default_factory=dict)
    channel: str | None = None
    language: str | None = None
    msisdn: str | None = None
    case_id: str | None = None
    subscriber_ref: str | None = None
    ignore_quiet_hours: bool = False


class PreferencesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscriber_ref: str
    language: str = "en"
    channel_order: list[str] = Field(default_factory=lambda: ["app", "sms", "whatsapp"])
    enabled: bool = True


def _build_router() -> APIRouter:
    router = APIRouter(tags=["notifications"])

    @router.post("/v1/notifications/send")
    def send_route(body: SendBody) -> dict[str, Any]:
        try:
            record = send_notification(
                template_id=body.template_id,
                params=body.params,
                channel=body.channel,
                language=body.language,
                msisdn=body.msisdn,
                case_id=body.case_id,
                subscriber_ref=body.subscriber_ref,
                ignore_quiet_hours=body.ignore_quiet_hours,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"notification": record.to_dict()}

    @router.get("/v1/notifications/status/{notification_id}")
    def status_route(notification_id: str) -> dict[str, Any]:
        record = get_status(notification_id)
        if record is None:
            raise HTTPException(status_code=404, detail="notification not found")
        return {"notification": record.to_dict()}

    @router.put("/v1/notifications/preferences")
    def prefs_route(body: PreferencesBody) -> dict[str, Any]:
        svc = get_notifications()
        prefs = Preferences(
            language=body.language,
            channel_order=body.channel_order,
            enabled=body.enabled,
        )
        svc.set_preferences(body.subscriber_ref, prefs)
        return {
            "subscriber_ref": body.subscriber_ref,
            "preferences": {
                "language": prefs.language,
                "channel_order": prefs.channel_order,
                "enabled": prefs.enabled,
            },
        }

    return router


class NotificationsModule:
    name = "notifications"
    schema = "notifications"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("notifications.quiet_hours.start", "21:00", "Quiet hours start (local)"),
            ConfigKey("notifications.quiet_hours.end", "07:00", "Quiet hours end (local)"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.provide(NotificationService, get_notifications())
        app.routes(_build_router(), prefix="")

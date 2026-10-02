"""Ed25519 hash-chained Trust Receipts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission
from clarity.modules.receipts.public import (
    get_receipt,
    issue_receipt,
    replay_receipt,
    verify_receipt,
)
from clarity.platform.app.module import AppBuilder, ConfigKey


class IssueReceiptBody(BaseModel):
    subscriber_ref: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    case_id: str | None = None
    action_type: str | None = None
    amount_lkr: str | None = None


def _build_router() -> APIRouter:
    router = APIRouter(tags=["receipts"])

    @router.post("/v1/receipts")
    def issue_route(body: IssueReceiptBody) -> dict[str, Any]:
        try:
            return issue_receipt(
                subscriber_ref=body.subscriber_ref,
                summary=body.summary,
                case_id=body.case_id,
                action_type=body.action_type,
                amount_lkr=body.amount_lkr,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.get("/v1/receipts/{receipt_id}")
    def get_route(receipt_id: str) -> dict[str, Any]:
        try:
            receipt = get_receipt(receipt_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="receipt not found") from error
        return receipt.to_dict()

    @router.get("/v1/receipts/{receipt_id}/html")
    def html_route(receipt_id: str) -> Response:
        try:
            receipt = get_receipt(receipt_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="receipt not found") from error
        return Response(content=receipt.html or "", media_type="text/html")

    @router.post("/v1/receipts/{receipt_id}/replay")
    def replay_route(receipt_id: str) -> dict[str, Any]:
        try:
            return replay_receipt(receipt_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="receipt not found") from error

    @router.get("/v1/verify/{receipt_id}")
    def verify_route(receipt_id: str) -> dict[str, Any]:
        return verify_receipt(receipt_id)

    return router


class ReceiptsModule:
    name = "receipts"
    schema = "receipts"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("receipts.verify_base", "http://localhost:8000/v", "Public verify URL base"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.routes(_build_router(), prefix="")

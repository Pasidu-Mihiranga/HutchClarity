"""IAM: OTP issuer, staff roles, guardian delegation, RLS vars."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from clarity.kernel.principal import Permission, Role
from clarity.modules.iam.domain.otp import OtpRefused
from clarity.modules.iam.public import (
    IamService,
    get_iam,
    principal_to_dict,
)
from clarity.platform.app.module import AppBuilder, ConfigKey


class OtpRequestBody(BaseModel):
    msisdn: str = Field(min_length=9, max_length=20)


class OtpVerifyBody(BaseModel):
    msisdn: str = Field(min_length=9, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class StaffTokenBody(BaseModel):
    roles: list[str] = Field(default_factory=lambda: ["agent"])


def _build_router() -> APIRouter:
    router = APIRouter(tags=["iam"])
    iam = get_iam()

    @router.post("/v1/auth/otp/request")
    def otp_request(body: OtpRequestBody) -> dict[str, Any]:
        try:
            result = iam.request_otp(body.msisdn)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except OtpRefused as error:
            raise HTTPException(status_code=429, detail=error.code) from error
        payload: dict[str, Any] = {
            "ok": result.ok,
            "msisdn_masked": result.msisdn_masked,
            "message": result.message,
        }
        if result.demo_code is not None:
            payload["demo_code"] = result.demo_code
        return payload

    @router.post("/v1/auth/otp/verify")
    def otp_verify(body: OtpVerifyBody) -> dict[str, Any]:
        try:
            principal = iam.verify_otp(body.msisdn, body.code)
            token = iam.issue_customer_token(principal)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except OtpRefused as error:
            raise HTTPException(status_code=401, detail=error.code) from error
        return {
            "token": token.value,
            "expires_at": token.expires_at.isoformat(),
            "principal": principal_to_dict(principal),
            "rls": iam.bind_rls(principal),
        }

    @router.post("/v1/auth/staff/token")
    def staff_token(body: StaffTokenBody) -> dict[str, Any]:
        try:
            roles = {Role(r) for r in body.roles}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"unknown role: {error}") from error
        issued = iam.issue_staff_token(roles)
        return {
            "token": issued.value,
            "expires_at": issued.expires_at.isoformat(),
            "principal": principal_to_dict(issued.principal),
            "rls": iam.bind_rls(issued.principal),
        }

    return router


class IamModule:
    name = "iam"
    schema = "iam"

    def permissions(self) -> list[Permission]:
        return []

    def config_keys(self) -> list[ConfigKey]:
        return [
            ConfigKey("iam.otp.ttl_seconds", 300, "OTP challenge lifetime"),
            ConfigKey("iam.customer_token.ttl_seconds", 600, "Customer session TTL"),
        ]

    def register(self, app: AppBuilder) -> None:
        app.provide(IamService, get_iam())
        app.routes(_build_router(), prefix="")

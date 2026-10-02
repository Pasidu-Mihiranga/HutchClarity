"""Public facade for the iam module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clarity.kernel.common import normalise_msisdn, subscriber_ref
from clarity.kernel.principal import Assurance, Principal, Role
from clarity.modules.iam.domain.guardian import GuardianError, GuardianRegistry
from clarity.modules.iam.domain.issuer import IssuedToken, TokenIssuer, new_staff_ref
from clarity.modules.iam.domain.otp import OtpRefused, OtpStore
from clarity.platform.config.settings import Profile, get_settings
from clarity.platform.vault.tokens import TokenVault

# Known demo MSISDNs used in lite walkthroughs (national last-4 / full forms).
_DEMO_SUFFIXES = ("4567", "5555", "1234", "9999")
_DEMO_MSISDNS = frozenset(
    {
        "+94771234567",
        "+94774445555",
        "+94770001234",
        "+94771119999",
    }
)


@dataclass
class OtpRequestResult:
    ok: bool
    msisdn_masked: str
    demo_code: str | None = None
    message: str = "code sent"


class IamService:
    """Facade: OTP, tokens, guardian, RLS bind helpers."""

    def __init__(
        self,
        *,
        otp: OtpStore | None = None,
        issuer: TokenIssuer | None = None,
        guardian: GuardianRegistry | None = None,
        vault: TokenVault | None = None,
        profile: Profile | None = None,
        hmac_key: bytes | None = None,
    ) -> None:
        settings = get_settings()
        self.otp = otp or OtpStore()
        self.issuer = issuer or TokenIssuer(secret=hmac_key or settings.subscriber_key_bytes)
        self.guardian = guardian or GuardianRegistry()
        self.vault = vault or TokenVault(hmac_key=hmac_key or settings.subscriber_key_bytes)
        self.profile = profile or settings.profile

    def request_otp(self, msisdn: str) -> OtpRequestResult:
        code = self.otp.request(msisdn)
        normalised = normalise_msisdn(msisdn)
        from clarity.kernel.common import mask_msisdn

        demo_code: str | None = None
        if self._expose_demo_code(normalised):
            demo_code = code
        return OtpRequestResult(
            ok=True,
            msisdn_masked=mask_msisdn(normalised),
            demo_code=demo_code,
        )

    def verify_otp(self, msisdn: str, code: str) -> Principal:
        normalised = self.otp.verify(msisdn, code)
        _, ref = self.vault.tokenise_msisdn(normalised)
        # Complete any pending guardian link for this child.
        try:
            self.guardian.confirm_after_otp(ref)
        except GuardianError:
            pass
        issued = self.issuer.for_customer(ref, assurance=Assurance.OTP)
        return issued.principal

    def issue_customer_token(self, principal: Principal) -> IssuedToken:
        ref = principal.subscriber_ref or principal.subject
        return self.issuer.for_customer(
            ref,
            assurance=principal.assurance,
            delegations=set(principal.delegations),
        )

    def issue_staff_token(self, roles: set[str] | set[Role] | list[str]) -> IssuedToken:
        parsed: set[Role] = set()
        for role in roles:
            if isinstance(role, Role):
                parsed.add(role)
            else:
                parsed.add(Role(str(role)))
        if not parsed or Role.CUSTOMER in parsed:
            # Staff issuer never mints customer-only tokens via this path.
            parsed = {r for r in parsed if r is not Role.CUSTOMER} or {Role.AGENT}
        return self.issuer.for_staff(new_staff_ref(), roles=parsed)

    def bind_rls(self, principal: Principal) -> dict[str, str]:
        """Session variables for Postgres RLS. Domain never sees raw MSISDN."""
        subject = principal.subscriber_ref or principal.subject
        role_csv = ",".join(sorted(r.value for r in principal.roles))
        delegations = ",".join(sorted(principal.delegations))
        return {
            "app.subject": subject,
            "app.actor": principal.actor_ref or principal.subject,
            "app.roles": role_csv,
            "app.delegations": delegations,
            "app.assurance": principal.assurance.value,
        }

    def ref_for(self, msisdn: str) -> str:
        return self.vault.ref_for(msisdn)

    def _expose_demo_code(self, msisdn: str) -> bool:
        if self.profile is Profile.PROD:
            return False
        # Lite (and full): always for known demos; lite also always exposes.
        if self.profile is Profile.LITE:
            return True
        return msisdn in _DEMO_MSISDNS or msisdn.endswith(_DEMO_SUFFIXES)


# Module-level singleton used by routes until DI is wired through AppBuilder.
_default: IamService | None = None


def get_iam() -> IamService:
    global _default
    if _default is None:
        _default = IamService()
    return _default


def reset_iam(service: IamService | None = None) -> None:
    global _default
    _default = service


def request_otp(msisdn: str) -> OtpRequestResult:
    return get_iam().request_otp(msisdn)


def verify_otp(msisdn: str, code: str) -> Principal:
    return get_iam().verify_otp(msisdn, code)


def issue_staff_token(roles: set[str] | set[Role] | list[str]) -> IssuedToken:
    return get_iam().issue_staff_token(roles)


def bind_rls(principal: Principal) -> dict[str, str]:
    return get_iam().bind_rls(principal)


def principal_to_dict(principal: Principal) -> dict[str, Any]:
    return {
        "subject": principal.subject,
        "roles": sorted(r.value for r in principal.roles),
        "permissions": sorted(p.value for p in principal.permissions),
        "subscriber_ref": principal.subscriber_ref,
        "delegations": sorted(principal.delegations),
        "assurance": principal.assurance.value,
        "actor_ref": principal.actor_ref,
    }


__all__ = [
    "IamService",
    "OtpRefused",
    "OtpRequestResult",
    "bind_rls",
    "get_iam",
    "issue_staff_token",
    "principal_to_dict",
    "request_otp",
    "reset_iam",
    "subscriber_ref",
    "verify_otp",
]

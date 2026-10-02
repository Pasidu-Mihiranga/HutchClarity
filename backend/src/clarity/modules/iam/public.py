"""Public surface of the iam module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.iam.authorization import (
    AuthorizationPolicy,
    OpaAuthorizationPolicy,
    PythonAuthorizationPolicy,
)
from clarity.modules.iam.keycloak import CompositeTokenVerifier, KeycloakTokenVerifier
from clarity.modules.iam.otp import (
    OTP_CHALLENGES,
    OTP_REQUESTS,
    OtpRefused,
    OtpService,
    SimulatedInbox,
)
from clarity.modules.iam.tokens import (
    REFRESH_TOKENS,
    SESSIONS,
    IssuedToken,
    TokenInvalid,
    TokenIssuer,
    TokenVerifier,
)

__all__ = [
    "OTP_CHALLENGES",
    "OTP_REQUESTS",
    "REFRESH_TOKENS",
    "SESSIONS",
    "AuthorizationPolicy",
    "CompositeTokenVerifier",
    "IssuedToken",
    "KeycloakTokenVerifier",
    "OpaAuthorizationPolicy",
    "OtpRefused",
    "OtpService",
    "PythonAuthorizationPolicy",
    "SimulatedInbox",
    "TokenInvalid",
    "TokenIssuer",
    "TokenVerifier",
]

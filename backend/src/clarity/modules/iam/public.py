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
from clarity.modules.iam.directory import (
    LoginRefused,
    StaffDirectory,
    StaffDirectoryInvalid,
    StaffIdentity,
    hash_secret,
)
from clarity.modules.iam.grants import (
    GRANTS,
    AuditGrant,
    AuditGrants,
    GrantAwareAuthorizationPolicy,
    GrantNotFound,
    GrantRefused,
    GrantState,
    SubjectKind,
    is_subject,
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
    "GRANTS",
    "OTP_CHALLENGES",
    "OTP_REQUESTS",
    "REFRESH_TOKENS",
    "SESSIONS",
    "AuditGrant",
    "AuditGrants",
    "AuthorizationPolicy",
    "CompositeTokenVerifier",
    "GrantAwareAuthorizationPolicy",
    "GrantNotFound",
    "GrantRefused",
    "GrantState",
    "IssuedToken",
    "KeycloakTokenVerifier",
    "LoginRefused",
    "OpaAuthorizationPolicy",
    "OtpRefused",
    "OtpService",
    "PythonAuthorizationPolicy",
    "SimulatedInbox",
    "StaffDirectory",
    "StaffDirectoryInvalid",
    "StaffIdentity",
    "SubjectKind",
    "TokenInvalid",
    "TokenIssuer",
    "TokenVerifier",
    "hash_secret",
    "is_subject",
]

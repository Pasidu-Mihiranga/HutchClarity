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
from clarity.modules.iam.httpsms import HttpSmsDelivery, HttpSmsDeliveryFailed
from clarity.modules.iam.keycloak import CompositeTokenVerifier, KeycloakTokenVerifier
from clarity.modules.iam.oidc import (
    LOA_MFA,
    LOA_PASSWORD,
    LOGIN_TTL,
    PENDING_LOGINS,
    OidcError,
    OidcLogin,
    OidcSettings,
    PendingLogin,
    ProviderTokens,
    code_challenge_for,
    nonce_matches,
)
from clarity.modules.iam.otp import (
    OTP_CHALLENGES,
    OTP_REQUESTS,
    OtpRefused,
    OtpService,
    RoutedOtpDelivery,
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
    "LOA_MFA",
    "LOA_PASSWORD",
    "LOGIN_TTL",
    "OTP_CHALLENGES",
    "OTP_REQUESTS",
    "PENDING_LOGINS",
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
    "HttpSmsDelivery",
    "HttpSmsDeliveryFailed",
    "IssuedToken",
    "KeycloakTokenVerifier",
    "LoginRefused",
    "OidcError",
    "OidcLogin",
    "OidcSettings",
    "OpaAuthorizationPolicy",
    "OtpRefused",
    "OtpService",
    "PendingLogin",
    "ProviderTokens",
    "PythonAuthorizationPolicy",
    "RoutedOtpDelivery",
    "SimulatedInbox",
    "StaffDirectory",
    "StaffDirectoryInvalid",
    "StaffIdentity",
    "SubjectKind",
    "TokenInvalid",
    "TokenIssuer",
    "TokenVerifier",
    "code_challenge_for",
    "hash_secret",
    "is_subject",
    "nonce_matches",
]

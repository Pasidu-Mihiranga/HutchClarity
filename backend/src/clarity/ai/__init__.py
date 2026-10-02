"""The AI layer: language only, never authority (L3).

Code in here phrases, extracts and classifies. It never decides a cause, an
amount or an eligibility, and it cannot execute anything: that is I1, and the
import contracts enforce it by keeping this layer away from the tool layer's
capability surface.

The entry point is a **role**, not a model. ``RoleRouter.invoke`` takes a role
and walks the chain `config/ai/models.yaml` declares for it, so no model ID
appears in code (I12) and a deployment with no provider configured still gets an
answer (ADR-0009).
"""

from __future__ import annotations

from clarity.ai.buckets import Priority, ProviderQuota, QuotaExhausted, TokenBuckets
from clarity.ai.local import LOCAL_IMPLEMENTATIONS
from clarity.ai.roles import (
    LOCAL_PROVIDERS,
    NON_ANSWERING_PROVIDERS,
    ModelCatalogue,
    ModelConfigInvalid,
    ModelRole,
)
from clarity.ai.routing import RoleAnswer, RoleRouter

__all__ = [
    "LOCAL_IMPLEMENTATIONS",
    "LOCAL_PROVIDERS",
    "NON_ANSWERING_PROVIDERS",
    "ModelCatalogue",
    "ModelConfigInvalid",
    "ModelRole",
    "Priority",
    "ProviderQuota",
    "QuotaExhausted",
    "RoleAnswer",
    "RoleRouter",
    "TokenBuckets",
]

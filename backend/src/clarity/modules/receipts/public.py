"""Public surface of the receipts module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.receipts.openbao import OpenBaoSigningService, SignerUnavailable
from clarity.modules.receipts.render import (
    RendererUnavailable,
    RenderFormat,
    render,
)
from clarity.modules.receipts.repository import (
    BY_PLAN,
    RECEIPT_SEQUENCE,
    RECEIPTS,
    SUBSCRIBERS,
    SUPERSEDED,
    ReceiptRepository,
    StoredReceiptRepository,
)
from clarity.modules.receipts.service import (
    ReceiptService,
)
from clarity.modules.receipts.signing import (
    DevSigningService,
    SigningService,
    UnknownKeyId,
)

__all__ = [
    "BY_PLAN",
    "RECEIPTS",
    "RECEIPT_SEQUENCE",
    "SUBSCRIBERS",
    "SUPERSEDED",
    "DevSigningService",
    "OpenBaoSigningService",
    "ReceiptRepository",
    "ReceiptService",
    "RenderFormat",
    "RendererUnavailable",
    "SignerUnavailable",
    "SigningService",
    "StoredReceiptRepository",
    "UnknownKeyId",
    "render",
]

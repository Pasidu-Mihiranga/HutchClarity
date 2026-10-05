"""Public surface of the offers module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.offers.offers import (
    Check,
    Comparison,
    MatchThresholds,
    OfferRecord,
    Signal,
    SignalLexicon,
    Verdict,
    check_message,
    compare,
    term_weights,
)
from clarity.modules.offers.repository import (
    OFFERS,
    OfferRepository,
    StoredOfferRepository,
)
from clarity.modules.offers.service import (
    CALL_WORDS_KEY,
    CODE_WORDS_KEY,
    CONFIRM_KEY,
    HUTCH_HOSTS_KEY,
    PAYMENT_WORDS_KEY,
    REVIEW_KEY,
    URGENCY_WORDS_KEY,
    OfferPolicy,
    OfferRefused,
    OfferService,
)

__all__ = [
    "CALL_WORDS_KEY",
    "CODE_WORDS_KEY",
    "CONFIRM_KEY",
    "HUTCH_HOSTS_KEY",
    "OFFERS",
    "PAYMENT_WORDS_KEY",
    "REVIEW_KEY",
    "URGENCY_WORDS_KEY",
    "Check",
    "Comparison",
    "MatchThresholds",
    "OfferPolicy",
    "OfferRecord",
    "OfferRefused",
    "OfferRepository",
    "OfferService",
    "Signal",
    "SignalLexicon",
    "StoredOfferRepository",
    "Verdict",
    "check_message",
    "compare",
    "term_weights",
]

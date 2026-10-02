"""Rule detector package."""

from __future__ import annotations

from clarity.modules.detection.domain.rules.balance_burn_payg import BalanceBurnPaygDetector
from clarity.modules.detection.domain.rules.double_charge import DoubleChargeDetector
from clarity.modules.detection.domain.rules.fup_not_disclosed import FupNotDisclosedDetector
from clarity.modules.detection.domain.rules.fup_surprise import FupSurpriseDetector
from clarity.modules.detection.domain.rules.loan_recovery import LoanRecoveryDetector
from clarity.modules.detection.domain.rules.loan_stacking import LoanStackingDetector
from clarity.modules.detection.domain.rules.outage_credit import OutageCreditDetector
from clarity.modules.detection.domain.rules.outage_during_pack import OutageDuringPackDetector
from clarity.modules.detection.domain.rules.pack_mismatch import PackMismatchDetector
from clarity.modules.detection.domain.rules.pack_sunset import PackSunsetDetector
from clarity.modules.detection.domain.rules.payment_pending_settlement import (
    PaymentPendingSettlementDetector,
)
from clarity.modules.detection.domain.rules.post_pack_burn_risk import PostPackBurnRiskDetector
from clarity.modules.detection.domain.rules.social_pack_scope import SocialPackScopeDetector
from clarity.modules.detection.domain.rules.vas_renewal_unnotified import (
    VasRenewalUnnotifiedDetector,
)
from clarity.modules.detection.domain.rules.vas_silent_renewal import VasSilentRenewalDetector
from clarity.modules.detection.domain.rules.wrong_pack import WrongPackDetector
from clarity.modules.detection.domain.rules.wrong_pack_purchase import WrongPackPurchaseDetector

__all__ = [
    "BalanceBurnPaygDetector",
    "DoubleChargeDetector",
    "FupNotDisclosedDetector",
    "FupSurpriseDetector",
    "LoanRecoveryDetector",
    "LoanStackingDetector",
    "OutageCreditDetector",
    "OutageDuringPackDetector",
    "PackMismatchDetector",
    "PackSunsetDetector",
    "PaymentPendingSettlementDetector",
    "PostPackBurnRiskDetector",
    "SocialPackScopeDetector",
    "VasRenewalUnnotifiedDetector",
    "VasSilentRenewalDetector",
    "WrongPackDetector",
    "WrongPackPurchaseDetector",
]

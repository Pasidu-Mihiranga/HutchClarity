"""Public surface of the autopsy module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.autopsy.pipeline import (
    AutopsyReport,
    CleanComplaint,
    Cluster,
    ClusterStatus,
    Complaint,
    ComplaintAutopsy,
    Similarity,
    TrigramSimilarity,
    canonicalise,
    detect_language,
)
from clarity.modules.autopsy.repository import (
    CLUSTERS,
    COMPLAINTS,
    AutopsyRepository,
    StoredAutopsyRepository,
)
from clarity.modules.autopsy.review import (
    CONFIRMED_LABEL,
    HYPOTHESIS_LABEL,
    REJECTED_LABEL,
    ClusterReview,
    ClusterReviews,
    ReviewedCluster,
    ReviewRefused,
    staff_view,
)
from clarity.modules.autopsy.service import AutopsyService, BatchComplaint, ComplaintSource, Intake

__all__ = [
    "CLUSTERS",
    "COMPLAINTS",
    "CONFIRMED_LABEL",
    "HYPOTHESIS_LABEL",
    "REJECTED_LABEL",
    "AutopsyReport",
    "AutopsyRepository",
    "AutopsyService",
    "BatchComplaint",
    "CleanComplaint",
    "Cluster",
    "ClusterReview",
    "ClusterReviews",
    "ClusterStatus",
    "Complaint",
    "ComplaintAutopsy",
    "ComplaintSource",
    "Intake",
    "ReviewRefused",
    "ReviewedCluster",
    "Similarity",
    "StoredAutopsyRepository",
    "TrigramSimilarity",
    "canonicalise",
    "detect_language",
    "staff_view",
]

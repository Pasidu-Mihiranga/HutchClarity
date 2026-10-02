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
    canonicalise,
    detect_language,
)

__all__ = [
    "AutopsyReport",
    "CleanComplaint",
    "Cluster",
    "ClusterStatus",
    "Complaint",
    "ComplaintAutopsy",
    "canonicalise",
    "detect_language",
]

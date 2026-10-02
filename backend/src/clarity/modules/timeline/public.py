"""Public surface of the timeline module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.timeline.builder import (
    TimelineBuilder,
    TimelineRequest,
)

__all__ = [
    "TimelineBuilder",
    "TimelineRequest",
]

"""Public surface of the resolution module.

Other modules, the composition root and the interfaces import from here only
(enforced by tests/architecture/test_module_boundaries.py). Everything else in
this package is internal and may change without notice.
"""

from __future__ import annotations

from clarity.modules.resolution.service import ResolutionService

__all__ = ["ResolutionService"]

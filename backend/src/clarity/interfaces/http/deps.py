"""The assembled core, as a FastAPI dependency.

Its own module so more than one router can ask for it. `main.py` owns the app
and most of the routes; `staff_sso.py` owns the sign-in flow. Both need the
core, and neither should import the other to get it.

Keeping `ClarityDep` here rather than building it per router also keeps the
annotation resolvable. `from __future__ import annotations` turns every
annotation into a string that FastAPI resolves against the defining module's
namespace, so a type alias created inside a function is invisible by the time
it is needed and the whole OpenAPI document fails to generate. A module-level
alias has no such problem, and the failure it prevents is not a local one: it
takes out `/openapi.json`, the schema export and every test that reads them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from clarity.app.container import Clarity

#: Set by `create_app`, or built on first use by a process that never calls it.
_app_state: dict[str, Clarity] = {}


def get_clarity() -> Clarity:
    """The single assembled core this process serves."""
    if "clarity" not in _app_state:
        _app_state["clarity"] = Clarity()
    return _app_state["clarity"]


def set_clarity(clarity: Clarity) -> None:
    """Install the core this process serves. Called by `create_app`."""
    _app_state["clarity"] = clarity


ClarityDep = Annotated[Clarity, Depends(get_clarity)]


__all__ = ["ClarityDep", "get_clarity", "set_clarity"]

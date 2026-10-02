"""Write the OpenAPI schema to a file (B09).

The schema is the contract between the backend and every client, so it is
committed rather than fetched from a running server: a reviewer can see it
change in a diff, and CI can tell that a generated SDK is stale without
starting the app.

Run through ``make contracts``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

#: Committed next to the other contracts, not inside the backend package: it
#: belongs to both sides.
DEFAULT_TARGET = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


def export(target: Path = DEFAULT_TARGET) -> Path:
    app = create_app(Clarity(world=build_demo_world()))
    schema = app.openapi()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Sorted keys and a trailing newline: the file has to diff cleanly, or a
    # regeneration looks like a contract change every time.
    target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def check(target: Path = DEFAULT_TARGET) -> int:
    """Exit non-zero if the committed schema is not what the app serves now.

    Used by CI so a route added without re-exporting fails the build rather
    than leaving every client working from a stale contract.
    """
    if not target.exists():
        print(f"{target} does not exist: run make contracts", file=sys.stderr)
        return 1
    committed = target.read_text(encoding="utf-8")
    app = create_app(Clarity(world=build_demo_world()))
    current = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if committed != current:
        print(
            f"{target.name} is stale: the app serves a different schema.\n"
            "Run `make contracts` and commit the result.",
            file=sys.stderr,
        )
        return 1
    print(f"{target.name} matches the app's schema.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(check())
    written = export()
    print(f"wrote {written.relative_to(Path.cwd().parent)}", file=sys.stderr)

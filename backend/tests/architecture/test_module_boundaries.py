"""Module boundaries (enterprise-plan 18 section 2.2, 21 section 4).

Outside a module, only its ``public`` surface may be imported. The one
exception is the actions module's ``capability`` surface, which only the
``case`` module and the composition root may use, because it is the only code
that can move money.
"""

from __future__ import annotations

import ast
from pathlib import Path

import clarity

SRC = Path(clarity.__file__).parent
CAPABILITY_USERS = ("clarity.modules.case", "clarity.app")


def _module_of(path: Path) -> str:
    parts = path.relative_to(SRC.parent).with_suffix("").parts
    return ".".join(parts)


def _imports(path: Path) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
    return found


def _violations() -> list[str]:
    problems: list[str] = []
    for path in SRC.rglob("*.py"):
        importer = _module_of(path)
        own = importer.split(".")[2] if importer.startswith("clarity.modules.") else None
        for line, target in _imports(path):
            parts = target.split(".")
            if len(parts) < 3 or parts[:2] != ["clarity", "modules"] or parts[2] == own:
                continue
            surface = parts[3] if len(parts) > 3 else ""
            if surface == "public":
                continue
            if (
                parts[2] == "actions"
                and surface == "capability"
                and importer.startswith(CAPABILITY_USERS)
            ):
                continue
            problems.append(f"{importer}:{line} imports {target}")
    return problems


def test_modules_are_imported_only_through_their_public_surface() -> None:
    assert _violations() == []


def test_every_module_has_a_public_surface_and_a_module_doc() -> None:
    missing = [
        f"{module.name}/{name}"
        for module in (SRC / "modules").iterdir()
        if module.is_dir() and module.name != "__pycache__"
        for name in ("public.py", "MODULE.md")
        if not (module / name).exists()
    ]
    assert missing == []


def test_the_public_surface_of_actions_cannot_move_money() -> None:
    """``actions.public`` must not import the executing code, even indirectly."""
    from clarity.modules.actions import public

    imported = {target for _, target in _imports(Path(public.__file__))}
    for capability in ("layer", "confirmation", "budget", "capability"):
        assert f"clarity.modules.actions.{capability}" not in imported

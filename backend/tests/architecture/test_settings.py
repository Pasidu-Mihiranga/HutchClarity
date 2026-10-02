"""Only the composition root reads the environment (issue #15, B07; I20).

A driver that reads a variable itself is invisible to ``app/settings.py``, so
nobody can tell from one place how a deployment is configured, and a missing
value surfaces deep inside a request rather than at startup. It also makes a
profile leak into business code, which is what I20 forbids.
"""

from __future__ import annotations

import ast
from pathlib import Path

import clarity

SRC = Path(clarity.__file__).parent

#: The only package allowed to read the environment. ``settings.py`` declares
#: every variable; ``container.py`` is the composition root that applies them.
ALLOWED = ("app/settings.py", "app/container.py")

#: Names that read the environment, however they are reached.
ENV_READERS = frozenset({"environ", "getenv", "environb"})


def _env_reads(path: Path) -> list[str]:
    """Lines in this file that read a process environment variable."""
    found: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        # os.environ[...], os.environ.get(...), os.getenv(...)
        if isinstance(node, ast.Attribute) and node.attr in ENV_READERS:
            found.append(f"{path.name}:{node.lineno} reads os.{node.attr}")
        # from os import environ / getenv
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name in ENV_READERS:
                    found.append(f"{path.name}:{node.lineno} imports os.{alias.name}")
    return found


def test_no_module_outside_the_composition_root_reads_the_environment() -> None:
    offenders: dict[str, list[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = str(path.relative_to(SRC))
        if relative in ALLOWED:
            continue
        if reads := _env_reads(path):
            offenders[relative] = reads
    assert offenders == {}, (
        "these modules read the environment: declare the value in "
        "clarity/app/settings.py and pass it in from clarity/app/container.py"
    )


def test_every_setting_is_declared_with_its_variable_name() -> None:
    """A field with no alias would be read from a name nobody documented."""
    from clarity.app.settings import Settings

    missing = [
        name
        for name, field in Settings.model_fields.items()
        if field.alias is None or not field.alias.isupper()
    ]
    assert missing == [], "every Settings field needs an upper-case env alias"


def test_every_declared_variable_is_in_the_env_example() -> None:
    """``.env.example`` is the deployment contract, so it must be complete."""
    from clarity.app.settings import Settings

    example = (SRC.parents[2] / ".env.example").read_text(encoding="utf-8")
    declared = {field.alias for field in Settings.model_fields.values() if field.alias}
    documented = {
        line.split("=", 1)[0].strip()
        for line in example.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    assert declared - documented == set(), "these variables are missing from .env.example"

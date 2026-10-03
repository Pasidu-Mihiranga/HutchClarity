"""The licence gate refuses what it should and allows what it should (I17, B10).

The gate lives in `backend/scripts/check_licences.py` and runs only in the CI
`sbom` job, so a break in it is invisible until a push fails. It did break:
protobuf 7.x reports its licence as "3-Clause BSD License", which is
BSD-3-Clause spelled the other way round, and the build stopped on a naming
difference rather than on a licensing problem.

These tests pin both directions, because a gate that is only tested for what it
allows degrades into a rubber stamp.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_licences.py"
_spec = importlib.util.spec_from_file_location("check_licences", _SCRIPT)
assert _spec and _spec.loader
check_licences = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_licences)


def report(tmp_path: Path, *entries: dict[str, Any]) -> Path:
    path = tmp_path / "licences.json"
    path.write_text(json.dumps(list(entries)), encoding="utf-8")
    return path


def entry(name: str, licence: str, version: str = "1.0") -> dict[str, Any]:
    return {"Name": name, "Version": version, "License": licence}


@pytest.mark.parametrize(
    "licence",
    [
        "Apache Software License",
        "Apache-2.0",
        "BSD License",
        "BSD-3-Clause",
        "3-Clause BSD License",
        "2-Clause BSD License",
        "MIT License",
        "MPL-2.0",
        "PSF-2.0",
        "LGPL-3.0-only",
    ],
)
def test_a_neutral_osi_licence_passes(licence: str, tmp_path: Path) -> None:
    assert check_licences.check(report(tmp_path, entry("some-dep", licence))) == 0


def test_the_spelling_that_broke_the_build_passes(tmp_path: Path) -> None:
    """Regression: protobuf 7.36.2 failed the gate on wording, not licensing."""
    assert check_licences.check(report(tmp_path, entry("protobuf", "3-Clause BSD License"))) == 0


@pytest.mark.parametrize(
    "licence",
    [
        "Business Source License 1.1",
        "Server Side Public License (SSPL)",
        "Commons Clause",
        "GNU General Public License v3 (GPLv3)",
        "GNU Affero General Public License v3",
        "Elastic License 2.0",
    ],
)
def test_a_licence_that_takes_the_right_to_fork_away_is_refused(
    licence: str, tmp_path: Path
) -> None:
    assert check_licences.check(report(tmp_path, entry("captive", licence))) == 1


def test_an_unknown_licence_stops_the_build_rather_than_defaulting(tmp_path: Path) -> None:
    """A licence nobody has classified is a decision, not a default."""
    assert check_licences.check(report(tmp_path, entry("mystery", "Some Bespoke Licence"))) == 1


def test_a_refusal_wins_over_a_dual_licence_that_includes_it(tmp_path: Path) -> None:
    """Listing MIT alongside AGPL does not make a dependency safe to adopt."""
    assert check_licences.check(report(tmp_path, entry("dual", "MIT License; GNU Affero"))) == 1


def test_a_dual_licence_passes_on_the_permissive_half(tmp_path: Path) -> None:
    dual = report(tmp_path, entry("packaging", "Apache-2.0 OR BSD-2-Clause"))

    assert check_licences.check(dual) == 0


def test_the_project_itself_is_not_gated_on_its_own_licence(tmp_path: Path) -> None:
    assert check_licences.check(report(tmp_path, entry("hutch-clarity", "Proprietary"))) == 0


def test_a_named_exception_carries_a_reason(tmp_path: Path) -> None:
    """An exception is a decision someone made, so it is written down."""
    for package, reason in check_licences.EXCEPTIONS.items():
        assert reason.strip(), f"{package} is excepted with no reason given"


def test_one_bad_dependency_fails_a_report_full_of_good_ones(tmp_path: Path) -> None:
    path = report(
        tmp_path,
        entry("fine-one", "MIT License"),
        entry("fine-two", "Apache-2.0"),
        entry("captive", "Business Source License 1.1"),
        entry("fine-three", "BSD-3-Clause"),
    )

    assert check_licences.check(path) == 1

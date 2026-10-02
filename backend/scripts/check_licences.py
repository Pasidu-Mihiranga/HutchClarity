"""Fail if a dependency's licence is not neutral and OSI-approved (I17, B10).

Plan 19 section 1 sets the criteria: open standards, neutral governance, an
OSI-approved licence. The reason is specific rather than ideological. HUTCH has
to be able to run, fork and extract parts of this system without asking anyone's
permission, and a licence like BSL or SSPL takes that away later, after the code
is already written against it.

So the check is a gate, not a report. A new dependency either carries a licence
on the allowed list or the build stops and somebody decides deliberately.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: Licences that satisfy plan 19 section 1. Permissive and weak-copyleft only:
#: a runtime dependency under strong copyleft would reach the whole service.
ALLOWED = frozenset(
    {
        "Apache Software License",
        "Apache-2.0",
        "Apache 2.0",
        "BSD License",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC License (ISCL)",
        "ISC",
        "MIT License",
        "MIT",
        "MIT-0",
        "Mozilla Public License 2.0 (MPL 2.0)",
        "MPL-2.0",
        "Python Software Foundation License",
        "PSF-2.0",
        "The Unlicense (Unlicense)",
        "Historical Permission Notice and Disclaimer (HPND)",
        "GNU Lesser General Public License v3 (LGPLv3)",
        "LGPL-3.0",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
        "GNU Library or Lesser General Public License (LGPL)",
        # A permissive MIT variant; OSI-approved.
        "MIT-CMU",
        "HPND",
    }
)

#: Not a dependency: this project itself. Its own licence is a decision for the
#: repository, not something this gate should second-guess on every build.
OWN_PACKAGES = frozenset({"hutch-clarity"})

#: Named exceptions, each with the reason it is acceptable. An exception is a
#: decision someone made, so it carries a justification rather than a name.
EXCEPTIONS: dict[str, str] = {
    # Dual licensed; we rely on the Apache-2.0 half.
    "packaging": "Apache-2.0 OR BSD-2-Clause, both allowed",
    # The classifier is vague but the project is BSD-3-Clause.
    "qrcode": "BSD-3-Clause per the project metadata",
}

#: Licences that must never appear in the runtime path, with the reason.
REFUSED: dict[str, str] = {
    "Business Source License": "BSL is not OSI-approved and converts on a delay",
    "Server Side Public License": "SSPL is not OSI-approved",
    "Commons Clause": "Commons Clause removes the right to sell a service",
    "GNU General Public License": "strong copyleft reaches the whole service",
    "GNU Affero": "AGPL reaches a service offered over a network",
    "Elastic License": "not OSI-approved",
}


def _terms(licence: str) -> list[str]:
    """Split a licence field into the individual licences it names.

    ``pip-licenses`` reports either a list of classifiers joined by semicolons
    or an SPDX expression such as ``Apache-2.0 OR BSD-3-Clause``. Both mean "any
    one of these applies", so both are split the same way.
    """
    separated = licence.replace(";", ",").replace(" OR ", ",").replace(" or ", ",")
    # Parentheses are not stripped: a classifier name legitimately contains
    # them, as in "Mozilla Public License 2.0 (MPL 2.0)".
    return [part.strip() for part in separated.split(",") if part.strip()]


def _is_allowed(name: str, licence: str) -> tuple[bool, str]:
    if name in OWN_PACKAGES:
        return True, "this project, not a dependency"
    for refused, reason in REFUSED.items():
        if refused.lower() in licence.lower():
            return False, reason
    if name in EXCEPTIONS:
        return True, EXCEPTIONS[name]
    # Any one of the named licences being acceptable is enough.
    if any(term in ALLOWED for term in _terms(licence)):
        return True, ""
    return False, f"{licence!r} is not on the allowed list"


def check(report: Path) -> int:
    entries = json.loads(report.read_text(encoding="utf-8"))
    problems: list[str] = []
    for entry in entries:
        name = entry.get("Name", "?")
        licence = entry.get("License", "UNKNOWN")
        allowed, reason = _is_allowed(name, licence)
        if not allowed:
            problems.append(f"  {name} ({entry.get('Version', '?')}): {reason}")

    if problems:
        print(
            "These dependencies do not meet the licence criteria "
            "(I17, plan 19 section 1):\n" + "\n".join(sorted(problems)) + "\n\n"
            "Either replace the dependency, or add it to ALLOWED or EXCEPTIONS in "
            "backend/scripts/check_licences.py with the reason, and note it in the "
            "devlog.",
            file=sys.stderr,
        )
        return 1

    print(f"{len(entries)} dependencies checked, every licence is neutral and OSI-approved.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: check_licences.py <pip-licenses json>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(check(Path(sys.argv[1])))

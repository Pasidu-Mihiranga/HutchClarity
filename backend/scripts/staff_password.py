#!/usr/bin/env python3
"""Hash a staff password or step-up code for the staff directory file.

The directory stores only salted scrypt hashes (iam.directory). Read the secret
from stdin so it never lands in shell history or a process list:

  read -rs SECRET && printf '%s' "$SECRET" | python scripts/staff_password.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if "__file__" in globals():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from clarity.modules.iam.public import hash_secret


def main() -> None:
    secret = sys.stdin.read().rstrip("\n")
    if len(secret) < 12:
        raise SystemExit("use at least 12 characters")
    print(hash_secret(secret))


if __name__ == "__main__":
    main()

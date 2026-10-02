#!/usr/bin/env python3
"""Print a stub AI token-usage table (roles x tokens) for the demo.

This is a placeholder for measured numbers from scripts/measure_tokens.py.
It does not call any LLM provider.
"""

from __future__ import annotations

ROLES: list[tuple[str, int, int]] = [
    # role, input_tokens, output_tokens (stub demo figures)
    ("fast-text", 1200, 400),
    ("extract", 800, 120),
    ("reason", 0, 0),  # rules decide; reasoner unused in default demo
    ("verify", 0, 0),
]


def main() -> None:
    print("Hutch Clarity — stub token usage (demo)")
    print(f"{'role':<12} {'input':>8} {'output':>8} {'total':>8}")
    print("-" * 40)
    grand = 0
    for role, inp, out in ROLES:
        total = inp + out
        grand += total
        print(f"{role:<12} {inp:>8} {out:>8} {total:>8}")
    print("-" * 40)
    print(f"{'TOTAL':<12} {'':>8} {'':>8} {grand:>8}")
    print()
    print("Note: stub only. Run scripts/measure_tokens.py for measured zeros")
    print("when no model is configured (template path).")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate the labelled DATA01 fixture without real customer data."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clarity.integration.drivers.mock.synthetic_dataset import (  # noqa: E402
    generate_synthetic_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=1500)
    parser.add_argument("--start", type=datetime.fromisoformat)
    parser.add_argument("--end", type=datetime.fromisoformat)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dataset = generate_synthetic_dataset(
        count=args.size, seed=args.seed, start=args.start, end=args.end
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(dataset.canonical_json() + "\n", encoding="utf-8")
    print(
        f"SYNTHETIC dataset: {len(dataset.complaints)} complaints, "
        f"{len(dataset.events)} evidence events, digest {dataset.digest}"
    )


if __name__ == "__main__":
    main()

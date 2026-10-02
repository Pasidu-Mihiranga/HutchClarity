#!/usr/bin/env python3
"""Seed the synthetic HUTCH store (Postgres or SQLite via DATABASE_URL).

Usage:
  make seed
  DATABASE_URL=postgresql+psycopg://clarity:clarity@localhost:5432/clarity make seed
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clarity.integration.drivers.mock.store import (  # noqa: E402
    create_schema,
    reset_engine,
    save_complaints,
    save_network,
    save_world,
    session_scope,
    upsert_knowledge,
)
from clarity.integration.drivers.mock.store.knowledge import KNOWLEDGE_ARTICLES  # noqa: E402
from clarity.integration.drivers.mock.store.volume import (  # noqa: E402
    generate_complaints,
    generate_volume_customers,
)
from clarity.integration.drivers.mock.world import DEMO_NOW, build_demo_world, ref_for  # noqa: E402


def main() -> None:
    reset_engine()
    create_schema()
    world = build_demo_world(now=DEMO_NOW, persist=False)
    generate_volume_customers(world, count=40)
    dilani_ref = ref_for("+94771234567")
    with session_scope() as session:
        save_world(session, world)
        save_network(
            session,
            dilani_ref,
            status="outage",
            text="Evening congestion in Colombo South.",
            eta="cleared",
            occurred_at=DEMO_NOW - timedelta(days=4),
        )
        save_network(
            session,
            dilani_ref,
            status="clear",
            text="No outage in your area right now.",
            eta=None,
            occurred_at=DEMO_NOW - timedelta(hours=1),
        )
        upsert_knowledge(session, KNOWLEDGE_ARTICLES)
        save_complaints(session, generate_complaints(2000))
    print(
        f"Seeded {len(world.accounts())} customers, "
        f"{len(KNOWLEDGE_ARTICLES)} knowledge articles, "
        "2000 historical complaints."
    )


if __name__ == "__main__":
    main()

"""Every stored collection has an owning module (I6, B05, ADR-0013).

This is the guard that was missing. `ALL_COLLECTIONS` in the composition root
and `OWNERS` in the platform are two lists that have to agree, and nothing
checked that they did. Four modules (knowledge, autopsy, deskops, insights)
shipped collections that no module owned, so `create_schema` raised
`UnknownCollection` and the whole `full` profile could not start. It passed
`make check` because the only test that touched the mapping needed PostgreSQL
and therefore skipped.

These tests need no database on purpose. A data-ownership rule that is only
enforced in a lane most runs skip is not enforced.
"""

from __future__ import annotations

import pytest

from clarity.app.collections import ALL_COLLECTIONS
from clarity.platform.persistence.schemas import (
    CUSTOMER_SCOPED,
    OWNERS,
    UnknownCollection,
    owner_of,
    schema_of,
    table_of,
)

MODULES = "backend/src/clarity/modules"


@pytest.mark.parametrize("collection", ALL_COLLECTIONS)
def test_every_stored_collection_has_an_owner(collection: str) -> None:
    """A table with no owner is a table with no access rules."""
    assert owner_of(collection), collection


def test_a_collection_no_module_claims_is_refused_not_defaulted() -> None:
    with pytest.raises(UnknownCollection, match="no module owns"):
        owner_of("nobody.rows")


@pytest.mark.parametrize("collection", ALL_COLLECTIONS)
def test_a_collection_is_named_for_the_module_that_owns_it(collection: str) -> None:
    """The prefix is the ownership claim, so the two cannot drift apart."""
    assert collection.split(".", 1)[0] == owner_of(collection)


def test_every_owner_is_a_real_module_or_the_platform(request: pytest.FixtureRequest) -> None:
    root = request.config.rootpath
    for prefix, owner in OWNERS.items():
        if owner == "platform":
            continue
        package = root / "src" / "clarity" / "modules" / owner
        assert package.is_dir(), f"OWNERS maps {prefix!r} to a module that does not exist: {owner}"


def test_no_owner_entry_is_dead() -> None:
    """A prefix nothing stores is a rule nobody reads. Remove it instead."""
    used = {collection.split(".", 1)[0] for collection in ALL_COLLECTIONS}
    assert set(OWNERS) == used


def test_every_customer_scoped_collection_is_actually_stored() -> None:
    """Row-level security on a table that does not exist protects nothing."""
    assert set(ALL_COLLECTIONS) >= CUSTOMER_SCOPED


def test_each_collection_maps_to_a_distinct_table() -> None:
    """Two collections sharing one table would silently merge their rows."""
    tables = [f"{schema_of(c)}.{table_of(c)}" for c in ALL_COLLECTIONS]
    assert len(set(tables)) == len(tables)


def test_the_modules_that_shipped_unowned_collections_stay_owned() -> None:
    """Regression: these four broke the `full` profile and `make check` missed it."""
    for prefix in ("knowledge", "autopsy", "deskops", "insights"):
        assert prefix in OWNERS, f"{prefix} lost its schema owner again"

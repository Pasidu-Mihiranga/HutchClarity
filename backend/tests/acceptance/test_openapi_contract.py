"""The /v1 contract as a reviewed snapshot (R0).

The OpenAPI document is reduced to what clients depend on: each operation's
parameters, request body and success response, and each schema's fields and
required fields. Any difference fails the build until the snapshot is
regenerated on purpose:

    UPDATE_GOLDEN=1 make test

A regenerated snapshot is a contract change: say so in CHANGELOG.md and update
the consumers (frontend SDK, MCP, MODULE.md).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world
from clarity.interfaces.http.main import create_app

GOLDEN = Path(__file__).parent / "golden" / "openapi-contract.json"


def _ref(schema: dict[str, Any] | None) -> str | None:
    if not schema:
        return None
    if "$ref" in schema:
        return str(schema["$ref"]).rsplit("/", 1)[-1]
    if schema.get("type") == "array":
        return f"array[{_ref(schema.get('items'))}]"
    return str(schema.get("type", "object"))


def contract() -> dict[str, Any]:
    document = create_app(Clarity(world=build_demo_world())).openapi()
    operations: dict[str, Any] = {}
    for path, methods in sorted(document["paths"].items()):
        for method, op in sorted(methods.items()):
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {})
            success = next(
                (code for code in sorted(op.get("responses", {})) if code.startswith("2")), None
            )
            response = (
                op["responses"][success].get("content", {}).get("application/json", {})
                if success
                else {}
            )
            operations[f"{method.upper()} {path}"] = {
                "parameters": sorted(
                    f"{p['in']}:{p['name']}{'' if p.get('required') else '?'}"
                    for p in op.get("parameters", [])
                ),
                "request": _ref(body.get("schema")),
                "status": success,
                "response": _ref(response.get("schema")),
            }
    schemas = {
        name: {
            "fields": sorted(spec.get("properties", {})),
            "required": sorted(spec.get("required", [])),
        }
        for name, spec in sorted(document.get("components", {}).get("schemas", {}).items())
    }
    return {"operations": operations, "schemas": schemas}


def test_the_v1_contract_matches_the_reviewed_snapshot():
    current = contract()
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert current == expected, (
        "the /v1 contract changed; if deliberate, run UPDATE_GOLDEN=1 make test "
        "and record the change in CHANGELOG.md"
    )

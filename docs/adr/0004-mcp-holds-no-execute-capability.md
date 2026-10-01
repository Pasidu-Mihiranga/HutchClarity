# 0004 - The MCP server holds no capability to execute

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | `docs/enterprise-plan/07-mcp.md` §10.4; `docs/improvement-plan.md` F2, A2 |

## Context
"Rules decide, the LLM explains" is the project's central claim, and the MCP
server is where a model meets the system. The tool catalogue already exposed
reads and `propose_action` only, and a test asserted no tool **name** contained
"execute", "confirm" or "approve".

That was not enough. The server was constructed with the whole `CaseService`,
which exposes `confirm_and_execute`, `approve_and_execute`, `auto_fix` and a
`tools` accessor returning the `ToolLayer` (and so `authorise_auto_fix`, which
mints a system confirmation token). Nothing called them, so the system was safe
in practice - but safety was a convention, and one edit inside the MCP package
could have moved money with every test still green.

## Decision
MCP receives `MCPCaseView`: a protocol offering reads and `propose` and nothing
else, implemented by an adapter that holds the case service privately. The
`tools` accessor is removed from `CaseService`. Two tests enforce it: an AST
scan of the MCP package for forbidden method names, and a reflection check that
the object MCP holds exposes none of them. An `import-linter` contract stops
`clarity.mcp` and `clarity.ai` importing the tool layer's capability modules.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Keep passing CaseService, rely on review | A security property that depends on nobody making a mistake is not a property |
| Put MCP in its own process calling REST | Stronger, and the right production answer (the alternative design's ADR-0008). Deferred: it needs auth (Phase 3) to be meaningful, and the capability boundary is what actually prevents the risk. |

## Consequences
Adding an MCP tool that needs new data means widening the view deliberately, in
a reviewed change. That friction is the point.

## Compliance
`tests/unit/test_mcp.py::test_the_mcp_package_contains_no_call_to_an_executing_method`
and `::test_the_object_mcp_holds_exposes_no_way_to_execute`.

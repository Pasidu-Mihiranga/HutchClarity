# [A04] MCP server over the network: SDK, Streamable HTTP, OAuth 2.1 resource server, new tools

| Field | Value |
|---|---|
| Wave | W2 AI foundation |
| Area | `interfaces.mcp` |
| Priority | P0 |
| Depends on | [M-IAM](M-IAM-identity-keycloak-for-staff-and-mcp-clients-opa.md) |
| Plan | 07 §10.7, ADR-0018 |
| Labels | `wave:w2`, `area:interfaces.mcp`, `priority:p0`, `type:feature` |

## Context
The MCP server is an in-process class; no external agent can connect.

## Scope
- `clarity-mcp` deployable using the MCP Python SDK (stateless), calling `/v1` through the generated client
- OAuth 2.1 resource server; token exchange downstream, no passthrough
- Add `search_knowledge` and `get_network_status`; MCP Apps cards for Why? and receipt

## Acceptance tests

| # | Given | When | Then | Where |
|---|---|---|---|---|
| 1 | an MCP client token for customer A | it asks for customer B's case | denied and audited | `backend/tests/unit/test_mcp.py` |
| 2 | the MCP Inspector or a desktop AI client | connected to the dev server | lists tools and gets a cited answer | `docs/walkthroughs WT-10` |
| 3 | every MCP tool | inspected | none executes money movement | `backend/tests/unit/test_mcp.py` |

## Definition of Done
- [ ] Every acceptance test above exists, fails before the change and passes after it
- [ ] `make check` green: lint, format, `mypy --strict`, import contracts, module boundaries, dependency map, all tests
- [ ] R0 acceptance suite green; OpenAPI snapshot unchanged, or regenerated on purpose with a CHANGELOG entry
- [ ] New call edges or events declared (plan 21 §11.2, §11.3; `test_module_dependencies.py`)
- [ ] Docs per the AGENTS.md sync matrix: `MODULE.md`, a devlog file, `ARCHITECTURE.md` / `docs/modules.md` when structure or status changes
- [ ] No secrets, no real personal data, simulated parts labelled; no em dash; commits follow AGENTS.md §10.1
- [ ] Walkthrough WT-10 verified

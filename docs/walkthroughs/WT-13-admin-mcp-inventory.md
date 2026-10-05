# Admin MCP Inspector connection

| Field | Value |
|---|---|
| Audience | platform admins / developers |
| Surfaces | Console Admin card · MCP Inspector · `clarity-mcp` |
| Related | [WT-10](WT-10-external-mcp-client.md), [ADR-0004](../adr/0004-mcp-holds-no-execute-capability.md), [ADR-0018](../adr/0018-mcp-stateless-resource-server.md), plan [07](../enterprise-plan/07-mcp.md) |

## What the Admin card shows

The **MCP Inspector** card on Admin is a connection pad, not an in-console
tool list. It:

- shows the Streamable HTTP URL for `clarity-mcp` (default
  `http://127.0.0.1:8099/mcp`, override with `NEXT_PUBLIC_MCP_URL`)
- opens the MCP Inspector with that URL and
  `transport=streamable-http` prefilled (default Inspector base
  `http://127.0.0.1:6274`, override with `NEXT_PUBLIC_MCP_INSPECTOR_URL`)
- copies the server URL to the clipboard

Tool names, levels and calls live in the Inspector UI after you connect.
The catalogue is still available at `GET /v1/mcp/tools` for API clients; the
Admin page no longer renders it inline.

## Prerequisites

```bash
make mcp                                          # clarity-mcp on :8099/mcp
npx @modelcontextprotocol/inspector               # Inspector UI on :6274
```

Then on Admin, press **Open MCP Inspector**. Authenticate with a staff-assist
token as in WT-10. Without a token the MCP surface returns 401 (I9).

## Invariants

- I1 / ADR-0004: MCP never executes L3/L4 money or service changes.
- I9: the MCP HTTP surface denies by default without a valid token.
- Templates (CX SMS wording) are **not** this card; they live in the content /
  template registry, not in the MCP tool list.

# 2026-10-05 - console - Admin MCP Inspector connect

| Field | Value |
|---|---|
| Author(s) | agent: Composer |
| Work package | console Admin (WT-13) |
| PR / commit | working tree |
| Units touched | frontend/apps/console |

## What changed
- Replaced the Admin **MCP tools** live inventory card with an **MCP Inspector**
  connection card: shows `clarity-mcp` URL, copy button, and deep-link open
  (`transport=streamable-http` + `serverUrl`).
- Added `NEXT_PUBLIC_MCP_URL` and `NEXT_PUBLIC_MCP_INSPECTOR_URL` to
  `frontend/.env.example`.
- Updated WT-13 Admin MCP walkthrough and staff-console step 4a.

## Why
Platform admins need to drive tools in the real MCP UI, not read a duplicate
list inside the console. WT-10 already documents Inspector against `:8099/mcp`.

## Decisions made
- Keep `GET /v1/mcp/tools` and SDK `listMcpTools` for API clients; stop rendering
  that inventory on Admin.
- Default Inspector base `:6274` (official `@modelcontextprotocol/inspector`).

## Docs updated
- [x] Walkthrough: WT-13-admin-mcp-inventory.md, WT-13-staff-console.md, WALKTHROUGHS.md
- [x] `frontend/.env.example`
- [ ] MODULE.md (N/A: console UI only)
- [ ] CHANGELOG.md / contracts (no `/v1` change)

## Tests
Not run (UI copy + link only). Manual: Admin → Open MCP Inspector after
`make mcp` and `npx @modelcontextprotocol/inspector`.

## Open issues / next step
None.

# 2026-10-05 - console - admin live MCP inventory

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | E2 / A04 (admin + MCP) |
| PR / commit | (local) |
| Units touched | frontend console, sdk |

## What changed
- Admin "MCP and templates" placeholder replaced with live **MCP tools** card.
- SDK: `listMcpTools(profile)` + `McpToolsInventory` / `McpToolView` types.
- Docs: `WT-13-admin-mcp-inventory.md`, WT-13 step 4a, WALKTHROUGHS index.

## Why
Operators need the real tool catalogue `clarity-mcp` would publish, not a
designed placeholder mixed with CX templates.

## Decisions made
- Profile picker: staff-assist (default), customer-assist, analytics.
- CX templates stay out of this card (different registry).

## Docs updated
- [x] WT-13-admin-mcp-inventory.md
- [x] WT-13-staff-console.md step 4a
- [x] docs/WALKTHROUGHS.md
- [x] Devlog (this file)

## Tests
- Spot-check: Admin as platform, MCP tools list loads for staff-assist.

## Open issues / next step
None.

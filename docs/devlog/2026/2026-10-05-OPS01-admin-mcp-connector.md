# 2026-10-05 - OPS01 - The admin MCP connector

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga |
| Work package | OPS01 (new, requested feature) |
| PR / commit | feat/admin-mcp-connector |
| Units touched | `clarity.interfaces.http`, console, SDK |

Written by an AI coding agent (Claude Code) under AGENTS.md §12.

## What changed

The console's admin page carried this:

> **MCP / templates** — Placeholder inventory - not connected to live MCP clients.
> · desk-copilot (designed) · receipt_issued · si/ta/en · otp_request · si/ta/en

**The server it was describing was real the whole time.** `clarity-mcp` is a
separate deployable (ADR-0018) serving MCP over Streamable HTTP, verifying
OAuth 2.1 bearer tokens as a resource server, checking the RFC 8707 resource
indicator, and choosing a tool profile from the token's scope. Ten tools, three
profiles, every call audited. None of it was reachable from the console.

- **`GET /v1/admin/mcp`** (`admin:manage`): the connector as configured —
  endpoint, transport, discovery URL, authorization parameters, and every
  profile with its scope, its case binding and its tools.
- **`GET /v1/admin/mcp/health`** (`admin:manage`): probes the MCP deployable
  and reports what came back. Separate from the inventory so the page loads
  without waiting on a network call.
- **`components/McpConnector.tsx`**: the panel. Server summary, a probe button,
  a tool table per profile with safety-level badges, and the guarantees a
  connected model is held to.
- **"Connect a system"**: a dialog that generates what another system needs —
  an MCP client config for OAuth-discovery clients, one for bearer-header
  clients, and the `curl` that fetches a token for the chosen profile. Each
  block copies to the clipboard.
- SDK: `mcpConnector()` and `mcpHealth()`.

## Decisions made

- **The tool list is read from the registry, never restated.** This is the
  whole point: a tool added to `ClarityMCPServer` appears on the page without
  anyone remembering to update it. The acceptance test asserts the page's list
  equals `list_tools(profile)` rather than a fixed count, so adding a tool does
  not fail the test and forgetting to update a page cannot pass it.
- **No secret, and a test that says so.** The client id, the issuer and the
  endpoints are public; the client secret stays in the operator's identity
  provider. The generated snippets reference `$CLARITY_MCP_SECRET` and
  `${CLARITY_MCP_TOKEN}` rather than carrying values (I14). A connection recipe
  is exactly the screen a secret gets added to for convenience, so the test
  checks the payload shape rather than trusting a reviewer to notice.
- **`admin:manage`, not public.** The endpoint, the scopes and the resource
  indicator together are the recipe for pointing a client at this system. Not
  a secret, and still not something an agent needs. `GET /v1/mcp/tools` stays
  public and unchanged: it lists one profile's tools and no connection detail.
- **The probe reports, never raises.** `clarity-mcp` is its own process, so a
  green console says nothing about it. An unreachable server comes back as
  `reachable: false`; a 500 would read as the console being broken rather than
  the thing it was asking about.
- **Two config shapes, because clients differ.** A client that supports OAuth
  discovery needs only the URL. One that takes a bearer header needs the header
  and a way to get a token. The dialog says which is which rather than picking
  for the operator.
- **`simulated` is read from `clarity.profile`.** The interfaces layer reads
  the profile in exactly one other place, `demo_only`, for the same kind of
  reason. I20 is about business code; this is a disclosure on an ops screen.

## Docs updated

- [x] This devlog
- [x] `CHANGELOG.md` (two new routes, two SDK methods)
- [x] `contracts/openapi.json` and the acceptance golden, regenerated
- [x] `frontend/packages/sdk` regenerated and the client extended
- [ ] MODULE.md: n/a (the MCP server is an interface, not a module)
- [ ] Walkthrough: WT-13 covers the console; a step for connecting a system is
      not written. Flagged below.

## Tests

- `tests/acceptance/test_mcp_connector_api.py`: 13. The inventory against the
  registry, the scope per profile, the case binding, I1 on the published
  surface, the absence of secrets, the probe's failure mode, and the permission
  gate against four staff roles plus anonymous.
- `tests/acceptance/test_route_contract.py`: both routes classified, passes.
- `ruff` clean; `mypy --strict` clean on the schemas.
- Frontend: `eslint` clean, `typecheck` clean in all five workspaces, console
  builds (`/admin` 5.76 kB).
- **Not run**: the full `make check`, `make e2e`. No browser test covers the
  new panel or the connect dialog.

## Open issues / next step

1. **An e2e spec** for the panel and the dialog, and an axe run on `/admin`
   with the dialog open (the E2 suite audits `/admin` and its flip dialog, not
   this one).
2. **A walkthrough step** in WT-13 for connecting a system end to end, which
   needs a running `clarity-mcp` and a configured issuer.
3. **The issuer is unset in the synthetic profiles**, so `token_endpoint` is
   null and the panel says so. Connecting a real client needs
   `CLARITY_KEYCLOAK_ISSUER` and the `clarity-mcp` client secret from the
   realm. **REQUIRES HUTCH CONFIRMATION** for the production realm.
4. **Scope registration.** The three profile scopes
   (`clarity.customer-assist`, `clarity.staff-assist`, `clarity.analytics`)
   must exist as client scopes in the realm for a token to carry one. The
   shipped `config/keycloak/clarity-realm.json` does not define them; the panel
   publishes the names a realm has to provide.

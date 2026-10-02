# 2026-10-03 - A04 - MCP server over the network

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) |
| Work package | A04 (`docs/backlog/issues/A04-mcp-server-over-the-network-sdk-streamable-http.md`, #8) |
| PR / commit | not committed |
| Units touched | interfaces.mcp, entrypoints, app.mcp_view, integration.drivers.mock, config/keycloak |

## What changed

- **New deployable `clarity-mcp`**: `interfaces/mcp/app.py` builds a Starlette
  app serving MCP over Streamable HTTP at `/mcp`, stateless, via MCP SDK 2.2.
  Entry point `entrypoints/mcp_asgi.py`, plus `make mcp`.
- **OAuth 2.1 resource server**: `interfaces/mcp/resource_server.py` adapts the
  existing `KeycloakTokenVerifier` to the SDK's `TokenVerifier` protocol;
  `interfaces/mcp/auth.py` maps a scope onto a tool profile and reads the case
  binding from a claim.
- **No token passthrough**: `interfaces/mcp/exchange.py` implements RFC 8693.
  Unconfigured means refused, not forwarded.
- **Tool listings filtered by profile** as well as refused on call.
- **New tools** `search_knowledge` and `get_network_status`.
- **MCP Apps cards** `ui://clarity/why-card` and `ui://clarity/receipt`.
- **Keycloak realm**: three profile client scopes and a realm-roles mapper.
- **`MCPCaseView` gained `network_status`** (see CHANGELOG for the surface note).

## Why

Issue #8: the MCP server was an in-process class, so no external agent could
connect. ADR-0018 and plan 07 §10.6-10.7 set the shape.

## Decisions made

- **The authorization core was not rewritten.** `ClarityMCPServer` already was
  the tested chokepoint, so the network layer derives a principal and calls it.
  Adding a transport should add a way in, not a new way to be allowed.
- **Two profile scopes are refused, not narrowed.** Picking the narrowest would
  let a client registered with two scopes work with the wrong tool set and
  nobody find out. A denial is noisy, and noisy is right for a misconfiguration.
- **Every tool has an explicit typed signature**, so the published JSON schema
  is reviewable in a diff. `propose_action` publishes no amount parameter: I1 in
  the contract, not only in the handler.
- **`search_knowledge` cites `rule_id@version`.** Only 1 of 10 rule packs states
  a `legal_basis`, so citing that would have made the tool nearly empty, and
  filling the other nine in would be inventing regulations (I16). The governed
  artefact is itself a checkable citation; `legal_basis` rides along when the
  rule states one and is `null` otherwise.
- **The retrieval corpus is interim.** The tool contract is the final one from
  plan 07 §11.1, backed by the rule catalogue until K01-K03 land the RAG
  service. The contract stays stable when the backend is swapped.
- **Denials are `ToolError`, not `MCPError`.** The SDK turns `ToolError` into
  `is_error` with the message in content and logs it at INFO with no traceback,
  which is what plan 07 §10.6 asks for. Any other exception would be a crash
  and the model would be told only "error executing tool".
- **No change to another module's public surface.** `search_knowledge` needed a
  rule's status, which `detection.public` does not export. Since `RuleStatus` is
  a `StrEnum` and `load_packs` already filters to active, comparing
  `pack.status.value` avoided widening `detection` for this issue.

## Defects this found

1. **An unbound customer MCP session could read every case.** `_authorize`
   compared the case binding only when `principal.case_id` was set, so a
   `customer-assist` principal with no binding skipped the check. In process
   the orchestrator always set it; over the network the binding comes from the
   token, so a client-credentials token with the customer scope was a universal
   read. Verified before the fix: an unbound principal returned 17 evidence
   events from a case it had no claim to. Now `SESSION_NOT_BOUND`.
2. **My own profile filter failed open.** The SDK returns `tools/list` as a
   plain dict, and the first version read `result.tools` with a
   `getattr(..., None)` fallback, so it found nothing on a dict and returned the
   listing untouched: every profile saw every tool. Caught by
   `test_a_customer_token_is_not_shown_staff_tools`. It now handles the wire
   shape and raises if it cannot read its input, because a security filter that
   waves through what it cannot parse is worse than one that fails.
3. **Declaring realm-level `clientScopes` silently removed Keycloak's
   built-ins.** Adding the three profile scopes replaced the whole list, so the
   built-in `roles` scope stopped existing, the clients' default assignment
   dropped it, and `realm_access` vanished from every token. Two M-IAM tests
   failed. Fixed by carrying a realm-roles mapper on each client so the roles
   claim does not depend on that list. This is the second time a realm import
   list replaced defaults rather than adding to them (the first was
   `realmRoles` on the service account).

## Non-vacuity

- The binding tests fail before the fix and the staff test passes throughout,
  so an over-broad "every session must be bound" fix would be caught.
- Replacing `self._verifier.verify(token)` with a no-op: exactly
  `test_a_token_signed_by_someone_else_is_refused` and
  `test_a_token_for_another_audience_is_refused` fail, so those two prove the
  resource server really validates.
- Removing the client scopes from the realm: 4 of the 5 real-Keycloak tests
  fail, and `test_the_scopes_really_come_from_the_realm_and_not_from_the_test`
  exists to name that cause directly.
- `test_a_valid_token_is_accepted_by_the_same_path` guards the three 401 tests
  against a server that refuses everything.

## Docs updated

- [x] `ARCHITECTURE.md` MCP row (no longer a gap; the remaining deviation named)
- [x] `CHANGELOG.md`, including the `MCPCaseView` surface change
- [x] Walkthrough [WT-10](../../walkthroughs/WT-10-external-mcp-client.md), verified, and the `docs/WALKTHROUGHS.md` row
- [x] `.env.example`: four `CLARITY_MCP_*` variables
- [x] `AGENTS.md` §13 and `make help`: `make mcp`
- [x] `plan.md`: A04 ticked
- [ ] `docs/modules.md` (no new module; `interfaces.mcp` is an interface)
- [ ] Plan via `CHANGES.md` (no plan change: this implements 07 §10.6-10.7)
- [ ] New module call edges (none: `interfaces` is above `modules`, and
      `test_module_dependencies.py` scans `modules/` only)

## Dependency licence check (I17)

`mcp>=2.2` (MCP Python SDK): **MIT**, OSI-approved and neutral. Added as the
`mcp` extra and pulled into `dev`, because the transport tests run under
`make check`.

## Tests

- `make check`: `1352 passed, 527 skipped` (was 1309 passed, 522 skipped before A04:
  +43 tests, and +5 skips because the real-Keycloak lane skips without
  `CLARITY_KEYCLOAK_URL`).
  Includes `ruff`, `ruff format`, `mypy --strict` over 200 files and the three
  import-linter contracts.
- `make test-full` with Postgres, Kafka, OPA, OpenBao and Keycloak:
  `1105 passed` in 77s, nothing skipped.
- `make contracts-check`: the `/v1` OpenAPI snapshot is unchanged, as expected:
  `clarity-mcp` adds no HTTP route to `clarity-api`.
- New: `tests/unit/test_mcp_network.py` (18, real MCP client against the real
  ASGI app), `tests/unit/test_mcp_auth.py` (22), 3 added to
  `tests/unit/test_mcp.py`, `tests/integration/test_mcp_keycloak.py` (5, real
  Keycloak).
- WT-10 walked by hand against the running deployable on :8099 with a real
  Keycloak token. Output recorded in the walkthrough §6.

**One transient failure worth recording.** On the first `make test-full`
immediately after `docker compose up -d --wait`,
`test_bus_parity.py::test_order_is_per_subject_not_global[kafka]` failed. It
then passed three times in a row on its own and in the next full run. The
broker answers its healthcheck before it has finished rebalancing, so this is
startup timing rather than a code defect. If it recurs in CI, the fix is a
readiness probe that waits for a group to be joined, not a retry.

## Open issues / next step

A04's Definition of Done is met with one deviation, recorded in
`ARCHITECTURE.md`: **`clarity-mcp` reads through the in-process narrow view
rather than calling `/v1` over HTTP.** Plan 07 §10.6 wants the deployable to
hold no data access and reuse `clarity-api`'s authorization and RLS. The
authorization boundary is real either way (`MCPCaseView` has no execute
capability), and the token exchange needed for the HTTP path is implemented and
tested, but the adapter that calls `/v1` is not written. There is no generated
Python client today; the committed OpenAPI snapshot and the TypeScript SDK are
the only generated artefacts. That is a separate piece of work and should be
its own issue.

Also noted while here, none of them regressions:

- `TokenBuckets` still declares no quotas, so the customer reserve is untested
  against a real budget.
- `Guard.check` is still not called by any request path, MCP included. An MCP
  tool taking free text (`search_knowledge`, `request_handoff`) is exactly where
  the injection guard belongs.
- No cassettes are committed yet.
- `AGENTS.md` §5 could use a row for "a Keycloak realm list" given that
  replacing Keycloak's defaults has now caused two separate failures.

Next: A05 (#9), the evaluation harness.

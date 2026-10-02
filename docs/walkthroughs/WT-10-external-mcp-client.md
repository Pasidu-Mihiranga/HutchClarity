# WT-10 - External MCP client asks "why was I charged?"

| Field | Value |
|---|---|
| Audience | developers / integration partners / judges |
| Journey | A registered AI agent connects to `clarity-mcp` over Streamable HTTP, lists tools and gets a cited answer |
| Plan | 07 §10.6, §10.7, §11.1; ADR-0018 |
| Status | verified |
| Last verified | 2026-10-03 (on `dabcb18` plus the A04 working tree) |

## 1. What you will see

`clarity-mcp` is a second deployable beside `clarity-api`. It speaks MCP over
Streamable HTTP at `/mcp`, is an OAuth 2.1 **resource server only**, and holds
no database. An agent authenticates with a token from Keycloak, is given the
tool set its scope selects, and can read evidence and propose remedies.

What it cannot do is move money. There is no execute tool, `propose_action`
takes no amount, and the published JSON schema never offers one.

## 2. Prerequisites

```bash
docker compose -f deploy/compose/full.yml up -d --wait keycloak
make mcp     # clarity-mcp on http://127.0.0.1:8099/mcp
```

`make mcp` sets the issuer to the simulated Keycloak realm, the resource
indicator to its own URL, and the allowed `Host` header to match.

## 3. Steps

| # | You do | API call | What to check |
|---|---|---|---|
| 1 | `curl -i http://127.0.0.1:8099/mcp` | `GET /mcp` with no token | **401**. The server is deny by default (I9) |
| 2 | Mint a token | `POST /realms/clarity/protocol/openid-connect/token` with `scope=clarity.staff-assist` | The `scope` claim carries `clarity.staff-assist`; `aud` is `clarity-api` |
| 3 | Connect a client | `initialize` | Server `clarity`; the instructions say it cannot move money |
| 4 | List tools | `tools/list` | 10 tools for staff, including `get_desk_queue` |
| 5 | List resources | `resources/list` | `ui://clarity/why-card` and `ui://clarity/receipt` (MCP Apps) |
| 6 | Ask a question | `search_knowledge` with `query` | Chunks, each with `source_id` of the form `RULE_ID@version` |
| 7 | Ask for a case that does not exist | `get_case_timeline` | `is_error` with `CASE_NOT_FOUND`, and **no stack trace** in the server log |
| 8 | Repeat step 2 with `scope=clarity.customer-assist`, then call `get_case_timeline` | `tools/list`, `tools/call` | `get_desk_queue` is **not listed**; a case-scoped call is refused with `SESSION_NOT_BOUND`, because a client-credentials token carries no case binding |

### Driving it

The MCP Inspector works against the same URL. For a scripted walk, the
automated version of steps 3 to 7 is
`backend/tests/unit/test_mcp_network.py::test_a_client_lists_tools_and_gets_a_cited_answer`,
and the Keycloak half of step 2 is
`backend/tests/integration/test_mcp_keycloak.py`.

## 4. What ran

```text
MCP client
  -> clarity-mcp  interfaces/mcp/app.py          Streamable HTTP, stateless
     -> resource_server.py                        bearer token -> AccessToken
        -> modules/iam  KeycloakTokenVerifier     signature, issuer, audience
     -> auth.py                                   scope -> profile, case claim
     -> interfaces/mcp/server.py                  authorize, run, audit
        -> app/mcp_view.py                        reads and propose only
```

## 5. What proves it worked

- Step 1 returns 401 before any tool exists in the conversation.
- Step 4's tool list differs between the staff and customer scopes, and the
  difference comes from the token, not from anything the client sent.
- Step 6's chunks each name `rule_id@version`, which you can look up in
  `rules/packs/` and check the wording against.
- Step 7 leaves no traceback in the log: the model gets a code and a safe
  message, never internals.
- Step 8 is the one worth dwelling on. A customer-scope token with no case
  binding reaches **nothing**. Before A04 the binding was only compared when
  present, so an unbound customer session could read every case in the system.

## 6. Observed on the verified run

```text
1. minted a staff-assist token from Keycloak
2. connected: clarity (protocol 2025-11-25)
3. listed 10 tools: explain_rule, get_case_timeline, get_cause_assessment,
   get_customer_safeguards, get_desk_queue, get_network_status,
   get_trust_receipt, propose_action, request_handoff, search_knowledge
4. UI cards: ui://clarity/receipt, ui://clarity/why-card
5. cited answer: 4 chunks
     VAS_NO_CONSENT@4  basis=Gazette 2316/14 - VAS requires consent + OTP
     DUPLICATE_VAS_CHARGE@1  basis=None
6. desk queue returned
7. unknown case refused: CASE_NOT_FOUND, no traceback in the server log
```

A `basis=None` is correct, not missing data: only `VAS_NO_CONSENT` states a
legal basis in its pack, and a legal basis is quoted, never inferred (I16).

## 7. Simulated parts

All HUTCH systems are `hutch-sim`. The Keycloak realm in
`config/keycloak/clarity-realm.json` is a **development** realm with a fixed
client secret; production registers the client with a generated secret from the
secrets store. `get_network_status` returns simulated coverage data and labels
it `simulated: true`. No real HUTCH identity provider is connected
(**REQUIRES HUTCH CONFIRMATION**).

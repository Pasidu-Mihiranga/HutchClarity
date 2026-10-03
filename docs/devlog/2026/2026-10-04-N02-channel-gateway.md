# 2026-10-04 - N02 - The channel gateway, and six ways to refuse a webhook

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | N02 (`docs/backlog/issues/N02-channel-gateway-whatsapp-sandbox-sms-and-ussd-si.md`, #40), Wave 4 |
| PR / commit | not committed at time of writing |
| Units touched | `interfaces.channels` (new), `app.settings`, `services/channel-gateway`, `Makefile`, `.env.example`, `backend/pyproject.toml` |

## What changed

- **`interfaces/channels/webhooks.py`**: signature verification, freshness and
  replay.
- **`interfaces/channels/window.py`**: the 24-hour customer service window.
- **`interfaces/channels/gateway.py`**: the app, driving the real conversation.
- **`services/channel-gateway/src/main.py`**: the deployable, five lines.
- `CLARITY_CHANNEL_WEBHOOK_SECRET`, `make channel-gateway`, and
  `clarity.interfaces.channels` added to the interface independence contract.

## What was there before

`services/channel-gateway/src/main.py` existed once and was deleted in
`3cca478`. It was a standalone FastAPI app with its own in-memory thread store
that minted case ids like `CASE-{uuid4().hex[:8]}`, so a WhatsApp conversation
existed only inside the gateway: nothing it said was backed by a case, a
decision, a rule or a receipt, and nothing it opened could ever be proved.

That is why the issue's context is one word, "Web only". The gateway was a
facade over nothing.

## Six refusals, and the order matters

A webhook endpoint is the one door into Clarity that anybody on the internet
can knock on. Everything else needs a session, a token or a staff role; this
takes a POST from a provider and starts a conversation with a customer. So most
of the work is refusing, and the interesting part is which refusals are not
obvious.

**1. No secret configured means reject everything.** The sharpest case of I9.
A gateway that accepted unsigned webhooks because nobody set a secret is worse
than one that is down, because it looks like it works. `/health` reports
`signing_configured` so the fault is visible before a provider's retries start
failing.

**2. The signature is computed over the raw body bytes.** The verifier runs
before parsing and takes `bytes`. This is the check that quietly dies if
somebody parses first: `json.dumps(json.loads(body))` changes whitespace and
key order, the digest stops matching, and the natural fix is to stop checking.
`test_a_tampered_body_is_rejected` signs one body and sends another.

**3. Comparison is constant time.** `==` on a digest leaks how many leading
bytes were right, which is enough to forge one byte at a time.

**4. The timestamp is inside the signed payload.** The signed string is
`timestamp.body`. Signing the body alone would let an attacker replay a valid
request forever and change the timestamp header freely, because nothing would
cover it.

**5. A stale timestamp is rejected even when the signature is good.** A valid
signature on an old payload is still a valid signature. Freshness is the only
thing that makes a captured request detectable, and a far-future timestamp is
refused too, because that is how a captured request is made to stay valid.

**6. A delivery id is accepted once.** A replay inside the freshness window has
a good signature and a good timestamp, so only remembering the id catches it.
The id is remembered **after** the other checks pass, so an attacker cannot
fill the bounded replay memory with ids of their choosing by sending garbage.

A rejected webhook returns `401` with a reason code and **echoes nothing from
its payload**, because the payload was never authenticated. There is a test
for that: a distinctive string in a rejected body must not appear in the
response.

## The 24-hour window is the provider agreeing with an invariant

WhatsApp allows a free-form reply only inside 24 hours of the customer's last
message; outside it, only an approved template. That is the same rule Clarity
already imposes on itself: I15 allows no free text to a customer except through
an approved template.

So the window is not a limitation to work around, and outside-the-window is the
*stricter* path rather than a problem to route around. Two decisions follow:

- **A dropped reply is reported, never substituted silently.** The tempting
  shortcut is to swap the composed reply for a template when the window has
  closed. That sends the customer wording nobody chose for their case while the
  audit shows a reply that was never delivered. The response carries
  `reply_was_templated` and `dropped_reply_because`.
- **Sending does not extend the window.** `ServiceWindows` has no method a send
  could call: the only way in is `opened`, and only inbound handling calls it.
  Getting that backwards would let a business keep its own window open
  indefinitely by messaging, which is what the rule exists to prevent. A test
  asserts the object has no `sent` attribute, which is a slightly odd
  assertion that pins a real design constraint.

Windows are keyed by `(channel, thread)` and not by subscriber: the same
customer on WhatsApp and on SMS has two windows, because the rule belongs to
the provider's conversation rather than to the person.

## It drives the real conversation, and closes AU01's loop

An inbound message resolves the number to a subscriber, finds that
subscriber's **open** case or opens one, and hands the text to C01's
orchestrator. C01 keyed conversation state by case id precisely so one
conversation could continue across channels; this is the piece that makes that
true for a basic phone, and `test_a_second_message_continues_the_same_case`
proves a WhatsApp thread is one case rather than one per message.

The gateway composes nothing and decides nothing. The reply it returns is the
one the orchestrator already verified, and the strongest thing a conversation
can do is propose (I1).

**It also produces `complaint.created`.** Plan 21 section 11.3 names channels
as that event's producer, and AU01 wired the autopsy consumer for it with
nothing producing it; the consumer has been sitting idle since. This closes the
loop. The event carries no message text, matching the contract autopsy relies
on, and a test asserts the payload still has no `text` field, because the day
somebody adds one is the day channels start putting customer words in the bus.

An unknown number is accepted, opens nothing and reveals nothing: the response
has the same shape whether or not the account exists, so the endpoint cannot be
used to find out which numbers are customers.

## The simulator is a separate path, not a flag

`POST /sim/{sms|ussd}` takes the same body with no signature, for the
basic-phone journey in a demo. It is its own route rather than a
`?verify=false` on `/webhooks/*`, because a bypass flag on the strict route is
the shape of hole that gets left on in production.
`test_the_simulator_is_a_separate_path_not_a_bypass_flag` sends the simulator's
unsigned body to the signed route and expects a 401.

## Two test bugs of mine, both worth recording

**A non-ASCII signature header cannot arrive over HTTP.** I wrote a route test
sending `sha256=ではない` to prove `hmac.compare_digest` could not be made to
raise. It failed with `UnicodeEncodeError` from the *test client*, because an
HTTP header cannot carry non-ASCII at all. The guard still belongs in the
verifier, which the simulator also calls and which a non-HTTP transport could
call later, so the test moved to the verifier and the route test now sends
non-hex ASCII, which is what a real probe looks like.

**An architecture test caught my own docstring.**
`test_only_the_composition_root_reads_the_profile` greps every file under
`clarity/` for the literal `CLARITY_PROFILE` and allows it only in
`app/settings.py` and `app/container.py`. My `/sim/*` docstring explained that
nothing outside the composition root may read that variable, and named it,
which tripped the test. The check greps rather than parses, which is blunt and
right: a grep cannot be fooled by `getattr(os.environ, ...)` or a name built at
runtime. The docstring was reworded; the HTTP layer avoids naming it for the
same reason.

**`msisdn_masked` is on `case.customer`, not on `case`.** My assertion read
`record.case.msisdn_masked` and pydantic said so plainly. Worth noting only
because the masked number being one level deeper is easy to get wrong in a
place where getting it wrong means asserting nothing.

## Where the tests live, and why not where the issue says

The issue puts acceptance 1 in `services/channel-gateway tests`. They are in
`backend/tests/unit/test_channel_gateway.py` instead, which is the choice H01
made for `hutch-sim`: the service is a five-line ASGI entry point and the app
is built by a factory inside `clarity.interfaces.channels`, so the logic is
covered by `make check` along with `mypy --strict` and the import contracts.

A test directory CI never runs is not a test directory. `make check` runs
`cd backend && pytest tests/...`, so a suite under `services/` would have been
green by never executing.

## Contract and plan notes

- **No `/v1` change and no snapshot change.** The gateway is its own ASGI app
  on its own port, not a route on the main API.
- **The interface independence contract now covers three interfaces**, not
  two: `clarity.interfaces.channels` is independent of `http` and `mcp`, so the
  gateway cannot start reaching into the HTTP layer's helpers.
- **No new event type.** `complaint.created` already existed in
  `contracts.events` and in plan 21 section 11.3 as produced by channels; N02
  is the producer that entry promised.
- **No new module edge.** The gateway is an interface and reads the composition
  root, typed loosely so the interface does not import the container and
  create a cycle.

## Docs updated

- This devlog, `services/channel-gateway/README.md`, `CHANGELOG.md`,
  `ARCHITECTURE.md`, `docs/modules.md`, `.env.example`
  (`CLARITY_CHANNEL_WEBHOOK_SECRET`), `plan.md` (#40 ticked).

## Tests run

- `make check`: **1775 passed, 544 skipped** (1745 before N02).
- `backend/tests/unit/test_channel_gateway.py`, 30 tests.
- Acceptance 1: a bad signature is rejected, asserted on the **world** as well
  as the status, because a 401 returned after the conversation had already run
  would satisfy a status check and still have opened a case for an
  unauthenticated caller.
- The other five refusals, plus the wrong secret, the tampered body, the
  missing signature, the unknown scheme, non-hex junk, and that a rejection
  echoes nothing from its payload.
- The other half: a verified webhook runs a real turn on a real case, a second
  message continues the same case, an unknown number opens nothing, the stored
  number is masked, and `complaint.created` is announced.
- The window: it opens on the customer's message, outside it only a template
  goes, a business-initiated conversation is template only, sending does not
  extend it, and each channel has its own.
- The simulator needs no signature and is not reachable as a bypass.
- The deployable boots: `services/channel-gateway/src/main.py` imported and
  `/health` called, reporting `signing_configured: false` with no secret set.
- The simulator is 404 in `prod` and reachable in the synthetic profiles.
- Non-vacuity: removing the signature comparison fails the three signature
  tests, acceptance 1 among them.

## Known gaps

- **No real provider.** This is a sandbox: nothing calls WhatsApp, and
  `/webhooks/*` is the shape a provider would POST to. The scheme is an
  **ASSUMPTION** following Stripe, Slack and the WhatsApp Cloud API, which
  differ only in header names and separators. **REQUIRES HUTCH CONFIRMATION**
  before it faces a real webhook; the checks do not change, only the parsing.
- **The replay guard and the windows are in process memory.** Two replicas
  would disagree: one that has not seen the inbound message says
  `TEMPLATE_ONLY`, which is the safe direction, and one that has not seen a
  delivery id would accept a replay, which is not. A shared store is the fix
  and B02's repositories are where it belongs.
- **No outbound send.** The gateway returns the reply in the webhook response,
  which a real provider integration would not: it would call the provider's
  send API. N01's dispatcher is the natural home for that and is wired for
  notifications rather than for conversational replies.
- **The window-closed template is unreviewed.** **ASSUMPTION** on the Sinhala
  and Tamil wording; the `language_review` gate (FE01, #28) is what clears it.
- **No rate limiting.** A public endpoint without it is a free denial of
  service, and the signature check runs an HMAC per request. X01 (#42) and X02
  (#43) own that.
- ~~`/sim/*` is not profile-gated.~~ **Fixed before committing.** I wrote this
  up as "the one gap here I would not ship without" and then did not ship it:
  an unsigned ingress on a `prod` deployment would undo every refusal above,
  so `/sim/*` now returns 404 when `clarity.profile is Profile.PROD`, using the
  same gate the HTTP layer's `demo_only` uses and reading the profile the
  composition root already resolved (I20). 404 rather than 403, so the route
  does not confirm it exists. Two tests: blocked in `prod` while the signed
  route still works, and reachable in the synthetic profiles so the gate
  cannot be "always 404".

## Next step

Wave 4 has one item left: #27 F01, foresight backtest and calibration. Then
Wave 5, where #28 FE01 and #42 X01 both touch this gateway: the unreviewed
template wording, and the missing rate limiting on a public endpoint that runs
an HMAC per request.

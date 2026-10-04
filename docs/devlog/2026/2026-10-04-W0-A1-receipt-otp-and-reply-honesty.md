# 2026-10-04 - W0 + A1 + A2 + A3 - receipt verdicts, OTP enumeration, the discarded reply, and the unguarded paths

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Opus 5 (Claude Code) |
| Work package | W0, A1, A2 and A3 of the demo-to-enterprise programme (plan file `quiet-gliding-nautilus`) |
| PR / commit | not committed |
| Units touched | interfaces.http, modules.conversation, customer-web, e2e, tests |

## What changed

**W0.3 - the customer receipt page claimed validity it never checked.**
- `GET /v1/receipts/{id}` returns `TrustReceipt` (`payload`, `payload_hash`, `signature`, `verify_url`). It carries no `valid`, no `chain_ok` and no top-level `summary`. The page read `receipt?.valid ?? receipt?.chain_ok ?? true`, so the expression resolved to `true` on **every** path, not only on error: each receipt rendered "Valid", "Signature Verified" and "Chain Intact" whether or not anything had been checked, and `String(receipt?.summary ?? "Trust receipt")` always printed the fallback. A failed load additionally fabricated a `Credit LKR 99.00 for silent VAS renewal` summary for an id that may never have been issued.
- The verdict now comes from `POST /v1/receipts/{id}/verify`, the only endpoint that computes one, read with an explicit `=== true`. Three outcomes, matching `apps/verify/app/r/[id]/page.tsx`: valid, invalid, and not checked (404 versus no answer, told apart).
- The document is fetched separately and only enriches the page (`payload.what_happened.summary`). It needs `receipt:read`, so a holder of the link without a session still gets a real verdict; a document that fails to load never changes it.
- `ValidityHero` gained a third state (`valid: boolean | null`) so "not checked" is renderable rather than collapsing into a pass.

**W0.2 - `POST /v1/auth/otp/request` was a subscriber directory.**
- It answered 404 "We could not find this Hutch number" for an unknown number and 200 for a real one: anyone could test which numbers are HUTCH customers, with no credentials, one number per request. `OtpRefused` states the opposite rule for the module ("a specific one would tell an attacker whether a number exists") and the channel gateway already keeps it.
- A challenge is now issued either way, so status, body shape, timing and the rate limit are the same for both. An unknown number then fails `verify` like any wrong code. The trail still records `unknown_number`, because the trail is not the attacker.

**A1 - the chat threw away the reply the backend worked hardest to make safe.**
- `ChatMessage` for the assistant carried only `kind`. `turn.reply` was declared on `TurnResponse` and read nowhere, so approved templates (I15), K03's verbatim grounded quotes, the verifier's substituted wording and the refusal text never reached the browser. The WhatsApp gateway returned it; the web app did not, so one question answered on two channels gave the customer different things.
- `reply` is now carried on the message (not on shared state, so a scrolled-back transcript keeps what was said) and rendered above the card.

**A2 - React decided whether the rule engine was asked.**
- `accountIntents` read `pack.used_pct >= 80`, duplicate payment amounts, consent flags and `vas_charge` rows and returned a map of booleans; `if (!can[clientIntent])` then short-circuited to a "could not confirm" card **without ever opening a case**. That is I1 inverted: deciding there is nothing to find is a decision, and it was being made by a heuristic in the browser over whatever the client happened to have loaded. FE01's own outcome section named it as an open violation.
- Deleted, with the gate. Every account-route question now reaches detection. When no rule matches, `decision/policy.py:155` already answers `Outcome.HANDOFF` with `HandoffReason.NO_CAUSE_FOUND`, and `pickResultKind` renders that as the handoff card, which offers a person. The conclusion the gate reached for is now reached by the component the invariant puts in charge of it, on system records rather than on a snapshot the browser may not have (I2).

**Windows portability of the test suite.** Four tests failed on Windows before any of the above, which made `make check` unusable on the development machine and hid real failures:
- `test_only_the_composition_root_reads_the_profile` and `test_no_module_accumulates_business_state_in_an_attribute` built their keys with `str(path.relative_to(...))`, which separates with a backslash on Windows, so no path matched their forward-slash allowlists and the composition root reported itself as an I20 offender. Both now use `as_posix()`.
- Two assertions on `st_mode & 0o777 == 0o600` cannot hold on NTFS, where `chmod` is a no-op. The mode assertion is now guarded by `os.name != "nt"`; the persistence half of each test, which is the part that catches the real regression, still runs everywhere, and the mode is still asserted on Linux and in CI.

**A3 - the anonymous turn surface was the one with no input inspection.**
- `/v1/conversation/turn` without a `case_id` (and `/v1/clarity/route`) runs `handle_turn`, which had no length cap, no forbidden-content check, no guard and no verifier, while the stateful branch beside it had all four. It also passed the request body's `facts` straight into composition, and `compose_reply` appends `facts["amount_lkr"]` for `UNEXPECTED_CHARGE` and `BALANCE_DEDUCTION_QUERY`. So an anonymous caller could post a figure and read it back as Clarity's own finding, with no session and no evidence behind it. That is I2 inverted, and the stateful path was already filtered and already tested (`test_a_client_supplied_figure_is_never_quoted_as_a_finding`).
- The HTTP layer now applies `_client_context` on both branches, so the two paths filter identically.
- `handle_turn` now runs the cheap refusals (empty, over `MAX_MESSAGE_CHARS`), refuses forbidden content via `find_forbidden`, neutralises injections via `inspect` (fallback intake, not a refusal, exactly as the orchestrator does), and verifies the composed reply with `verify_reply`, dropping to the figureless template on a failure.
- `MAX_MESSAGE_CHARS`, `REFUSALS`, `refusal_for` and `fallback_intake` moved from `orchestrator.py` into `service.py`, because `orchestrator` already imports from `service` and the dependency cannot run the other way. Both paths now share one definition, so a refusal cannot drift into different wording on one of them. `public.py` re-exports the same names from their new home, so the module's public surface is unchanged.
- Masking is deliberately **not** done on this path: `Masker` holds a token vault and belongs to the orchestrator, which has somewhere to put what it learns. Nothing on the stateless path is stored, and forbidden content is refused outright rather than masked, which is why that gap is survivable. Recorded here rather than left for a reader to notice.

## Why

W0.2 and W0.3 are live defects, not programme items: both are reachable on the deployed VPS today. W0.3 inverts the product's central promise, since a Trust Receipt that reports a verdict it did not compute is worse than no page. A1 is the highest value per day in the whole programme: one change makes every guarantee C01, K03 and both verifiers already establish visible to a customer for the first time.

The Windows fixes are not scope creep: verification step 2 of the programme is `make check`, and it could not pass on this machine for reasons unrelated to any change.

## Decisions made

- **The verdict and the document are two calls, not one.** Verification is public and authoritative; the document needs a permission and only adds detail. Folding them would have made an unauthenticated holder of a printed receipt unable to verify it.
- **`otp/verify` keeps its 404** for a number with no account. It is reachable only by someone who already proved possession of the phone, so it is not an oracle.
- **`/v1/me/family`'s 404 was left alone.** It sits behind `self:settings`, and telling a signed-in customer that a number they typed is not on HUTCH is the useful answer.
- Guarding a POSIX assertion by platform is not weakening a test (AGENTS.md §10): the OS cannot express the mode, so the assertion was failing for the platform rather than for the code. Skipping the whole test would have lost the persistence coverage, which is the half that catches the regression it was written for.

## Docs updated

- [x] MODULE.md of: `conversation`. A3 moved four names between files inside the module and added input inspection to `handle_turn`. The public surface is unchanged (`public.py` exports the same names), so no CHANGELOG entry, but the module's own description of what the stateless path does was wrong and is updated.
- [ ] ARCHITECTURE.md / modules.md: not needed, no status or structural change.
- [ ] Walkthrough: WT-02 and the receipt walkthrough should be re-verified when the browser suite is next run. Not done here.
- [ ] CHANGELOG.md / contracts: no `/v1` contract change. `otp/request` keeps its response model; only the status for an unknown number changed, which the OpenAPI snapshot does not describe.
- [ ] Plan via CHANGES.md: not needed.

## Tests

Added:
- `backend/tests/unit/test_iam.py::test_requesting_a_code_does_not_reveal_who_is_a_subscriber`
- `backend/tests/unit/test_iam.py::test_a_code_for_an_unknown_number_still_cannot_sign_anyone_in`
- `backend/tests/acceptance/test_flows.py`, four for the stateless path: `test_an_anonymous_caller_cannot_have_their_own_figure_quoted_back`, `test_the_stateless_path_refuses_a_message_it_cannot_read`, `test_the_stateless_path_refuses_a_one_time_code_instead_of_answering`, `test_the_stateless_path_does_not_let_held_text_choose_an_intent`. All four were confirmed to fail against the unfixed source (stash the four source files, run, restore) and pass after.
- `frontend/e2e/customer-receipt.spec.ts` (3 tests, mirroring `verify-receipt.spec.ts`)

Run:
- `ruff check .` and `ruff format --check .`: all checks passed, 377 files already formatted.
- `mypy`: success, no issues found in 234 source files.
- `lint-imports`: 3 contracts kept, 0 broken.
- `npx tsc -p apps/customer-web/tsconfig.json --noEmit`: clean. Note `npm run typecheck` does **not** cover the apps (programme item E5), so this was run directly.
- `pytest`: `2407 passed, 633 skipped in 98.56s`. No failures.
- `npm run build -w @clarity/customer-web`: all 9 routes compiled.

Before this change, on Windows, four tests failed on a clean tree at `e297f79`: `test_module_state.py::test_no_module_accumulates_business_state_in_an_attribute`, `test_api.py::test_only_the_composition_root_reads_the_profile`, `test_iam.py::test_a_persisted_issuer_key_keeps_sessions_across_a_restart`, `test_settings.py::test_configured_signing_key_survives_a_restart`. All four now pass.

The new e2e spec has **not** been executed: the Playwright suite needs `make dev-e2e` plus three Next.js servers, and `ARCHITECTURE.md:133` records that the browser suite has not been run end to end. It is written against the same helpers and `data-testid` conventions as the specs beside it, and it is unverified until that run happens. Said plainly rather than implied.

## Open issues / next step

1. **The dev staff identity routes are reachable in the `full` profile**, which is what the deployed VPS runs (`deploy/scripts/vps-bootstrap.sh`). `demo_only` gates `PROD` only, and AGENTS.md **I9 says exactly that** ("synthetic profiles (`demo`/`lite`, `full`) and return 404 in `prod`"), so the code matches its invariant. The exposure is a public deployment running a synthetic profile, not a code defect, and narrowing `demo_only` would leave the VPS with no staff sign-in until B1 lands. This needs a decision, not a patch: either the VPS stops being public, or the dev routes get a deployment-level credential, or B1 (Keycloak SSO) is pulled forward.
2. `POST /v1/auth/staff/session` still mints `Assurance.MFA_RECENT` from a request-body boolean. B2 replaces it.
3. **A2 changes case volume.** Every account-route question now opens a case, where previously the client gate suppressed some before any call. That is the intended architecture (a case is "one customer problem"), but it is a real behavioural change and the demo's case counts will move. Worth watching when the browser suite is next run.
4. **`npm run lint` is not merely unwired, it is unconfigured.** `next lint` in `apps/customer-web` prompts interactively to set ESLint up, so it would hang rather than fail in CI. Programme item E6 should configure it, not just invoke it.
5. The `ResultKind` values `confirm`, `grounded` and `refused` are still declared and still return `null` from the `ClarityMessageCard` dispatcher; flow artefacts still render only on the last message. C05 scope, folded into A7.
6. The repo's `.venv` was missing `google-auth`, a declared dependency, so the suite could not import at all. Installed locally; worth a `make setup` note if others hit it.

# 2026-10-04 - C05 - The chat was never on the flows

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | C05 (`docs/backlog/issues/C05-customer-chat-experience-on-flows-confirm-cards-.md`, #24), Wave 3 |
| PR / commit | not committed at time of writing |
| Units touched | `frontend/apps/customer-web`, `frontend/packages/i18n`, `frontend/e2e` (new), `Makefile` |

## The bug underneath the feature

The issue says "the chat UI renders single responses". It does, and the reason
turned out to be one line:

```ts
const facts = { case_id: cs.caseId, ... };
const turn = await fetchTurn(typed, lang, intentOverride, facts, app);
```

`POST /v1/conversation/turn` reads `case_id` from the **top level** of the body
and only then takes the stateful pipeline. The client sent it inside `facts`,
where the route never looks, so **every turn took the stateless path**: no
conversation state, no flow, no citations, no proposal, nothing to render. C01
through C03 and K03 all landed behind a route the UI was calling in a mode that
skipped them.

Nothing failed. The backend acceptance tests pass `case_id` correctly and have
been green throughout, the route is documented as doing exactly what it does,
and the UI looked fine because it drives its own client-side journey as a
fallback. A contract honoured by the tests and missed by the only real caller
is the kind of gap that needs a browser to see, which is why acceptance 1 is an
e2e and not another API test.

## What changed

- **`clarityChat.ts`**: `case_id` and `channel` at the top level; types for
  `FlowSnapshot`, `Citation`, `Verifier` and `Handoff`; the flow artefacts kept
  on the chat state instead of dropped.
- **`components/FlowCards.tsx`**: `FlowProgress`, `ConfirmCard`, `Citations`,
  `HandoffNotice`, `RefusedNotice`.
- **`packages/i18n`**: 42 new strings in en, si and ta, and `t` now
  interpolates `{placeholders}`.
- **`frontend/e2e/`** and `playwright.config.ts`: the browser suite.
- `make dev-e2e`, `make e2e`, `make e2e-install`.

## Decisions made

1. **The confirm card prints the amount and never composes one.** No rounding,
   no "about LKR 50", no currency inferred from a locale. I1 keeps amounts in
   the decision record, and a UI that formats one has invented a figure as
   surely as a model would.

2. **Confirming calls the server's confirm step.** There is no local "mark as
   done": the confirmation token is minted server side (ADR-0007) and nothing
   in the browser can mint one. The card reuses the existing `confirmFix`
   action rather than adding a second path to the same place.

3. **A citation is rendered whole**, version and clause included. `SIM-FUP@1`
   is checkable and "the terms" is not, and K03 went to some trouble to make
   each one verifiable.

4. **The journey is an ordered step list, not a progress bar.** A flow can exit
   early and legitimately: a dispute that explains and proposes nothing is a
   complete journey. A percentage would either overstate how far along somebody
   is or imply steps that will never run.

5. **Flow artefacts render on the newest card only.** On every card they would
   repeat the same journey state down the whole transcript, and a screen reader
   would read it once per turn.

6. **A refusal is shown, not swallowed.** The backend refuses for reasons a
   customer can act on (an OTP in a message, a reply that quoted a figure
   nothing decided), and a refusal they cannot see leaves them waiting for an
   answer that is not coming.

## Accessibility, which was worse than "not done"

Three things found while writing selectors for the e2e, all of them real:

- **The composer had no accessible name.** It had a placeholder, which is not a
  name: it disappears on the first keystroke and some screen readers never
  announce it. The one control on the screen was unnamed.
- **The login labels were not bound to their inputs.** Plain `<label>` with no
  `htmlFor`, so both fields on the sign-in screen were unlabelled and the
  labels read as loose text. Fixed with `htmlFor`/`id` and the right
  `autoComplete` values, which also makes one-time-code autofill work.
- **The transcript was not a live region.** A reply arriving while focus is in
  the composer was never announced. It is now `role="log"` with
  `aria-live="polite"`: polite rather than assertive, so a reply waits for the
  screen reader to finish rather than interrupting mid-sentence.

The e2e selectors are all role and label based for this reason. A suite that
selects by CSS class passes on a screen no screen reader can use, so writing
the test by accessible name is what found these.

## i18n

42 new keys in all three catalogues, in the shared `@clarity/i18n` package
rather than inline, which is what the issue asked for. `t` interpolates, so
`handoff.body` carries `{queue}` rather than being concatenated at the call
site.

The existing `~100` chat strings are still inline in `page.tsx` as a per
language `COPY` object. I did **not** migrate them: it is a mechanical change
across a 750-line file with no test coverage behind it, and doing it in the
same commit as a behaviour fix would make both hard to review. The new surface
is in the right place and the old surface is unchanged.

`packages/i18n/test/catalogues.test.mjs` is new, using `node:test` so it costs
no dependency. Four properties, and the third is the one worth having: `t`
falls back to English and then to the key, which is right at runtime and hides
a missing translation completely, so the test fails if more than a fifth of a
language's strings are byte-identical to English. It also checks that
placeholders match across languages, because a translation that drops `{queue}`
renders a sentence without the thing it was about.

## What I could not verify, and that matters here

**The Playwright suite has never been executed.** `npx playwright install
chromium` could not fetch the browser in this environment: fifteen minutes, no
output, 4 KB in the cache directory. So:

| Checked | How |
|---|---|
| The spec compiles and all 3 tests are discovered | `npx playwright test --list` |
| The app typechecks | `tsc --noEmit` on the app project, clean |
| The app builds | `next build`, compiled successfully |
| The i18n catalogues agree | `node --test`, 4 passing |
| The journey works over the API | the existing acceptance suite, green |
| **The journey works in a browser** | **not checked** |

The selectors, the test ids and the flow state names are therefore *believed*
correct and not *known* correct. `make e2e-install && make e2e` on a machine
with network access is what settles it, and the first run should be expected to
need selector fixes. I have not marked WT-02 re-verified for the browser steps
for the same reason; its table now says which half is verified.

This is the honest state of acceptance 1: the test exists, it is specific, and
it has not run.

## Two pre-existing problems found on the way

**The apps are never typechecked.** `npm run typecheck` covers
`packages/sdk/tsconfig.json` only, so no app is checked by CI or by
`make check`. `apps/customer-web` had a real type error sitting in it
(`(client as Record<string, unknown>).getCases?.()`, whose values are `unknown`
and so not callable). I fixed the one error because I needed a clean typecheck
to trust my own, and the missing coverage is the larger finding: adding the app
projects to `typecheck` would be a small change with an unknown blast radius
across three apps, so it wants its own issue rather than a quiet addition here.

**`npm run lint` has never run.** There is no ESLint config anywhere in
`frontend/`, so `next lint` prompts interactively and exits non-zero. Nothing
in CI or the Makefile calls it, so this has been true since the frontend
landed. Configuring ESLint for three apps and fixing whatever it finds is its
own task.

## Docs updated

- This devlog, `CHANGELOG.md`, `ARCHITECTURE.md`, `docs/WALKTHROUGHS.md`,
  `docs/walkthroughs/WT-02-vas-journey.md`, `plan.md` (#24 ticked).
- No backend `MODULE.md` change: no backend module changed.
- **No `/v1` contract change and no snapshot change.** The route already
  returned everything rendered here; C05 is the client finally sending the
  field that switches it on.
- No new event, no new module edge, no `.env.example` change.

## Tests run

- `make check`: **1679 passed, 544 skipped** (unchanged by C05, which is
  expected: nothing in the backend changed).
- `make contracts-check`: unchanged.
- `tsc --noEmit` on `apps/customer-web`: clean.
- `next build`: compiled successfully.
- `node --test` in `packages/i18n`: 4 passing.
- `npx playwright test --list`: 3 tests discovered in 1 file.
- `tests/acceptance` for the dispute, receipt and assistant journeys: green.

## Known gaps

- **The e2e has not run** (above). The single most important gap in this change.
- **WT-02's browser steps are unverified** and its table says so.
- The remaining chat strings are inline rather than in `@clarity/i18n`.
- The apps are not typechecked and ESLint is not configured (above).
- `FLOW_STEPS` in `FlowCards.tsx` duplicates the state names from
  `config/flows/*.yaml` in the client. A flow file renaming a state leaves the
  UI showing an unlabelled step, and nothing fails. The right fix is to serve
  the flow's steps from the API so there is one source; until then this is a
  copy, which is the same class of problem K02's `TOOL_ARGS` has and is worth
  solving the same way.
- `ConfirmCard` takes its amount from `cs.decision`, which the client fetched
  from the evaluate call, rather than from the proposal the flow returned. Both
  come from the server and agree today; one source would be better.

## Next step

Wave 3 is complete: C01 to C05 and K01 to K03 are all closed. The gaps worth
carrying forward are an embedding model (K02, K03), a recorded cassette so any
model path is exercised at all (C03, C04, K03), publishing flows and knowledge
sources through `PolicyGovernance` (C02, K01), and running this e2e.

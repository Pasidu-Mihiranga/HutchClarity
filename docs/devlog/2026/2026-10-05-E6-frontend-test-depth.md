# 2026-10-05 - E6 - A front end with tests, and a lint gate that runs

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga |
| Work package | Workstream E6 (enterprise UI plan) |
| PR / commit | feat/enterprise-ui |
| Units touched | frontend (all apps and packages), frontend/e2e, .github/workflows, config/staff |

Written by an AI coding agent (Claude Code) under AGENTS.md §12.

## What changed

**Component tests where there were none.** Vitest, jsdom and Testing Library were in `packages/ui` only. Both apps have them now, mirroring that config (esbuild's automatic JSX, so no `@vitejs/plugin-react` and no extra licence note under I17).

- console, 17 tests: `useRovingRows` (one tab stop, Up and Down clamped at the ends, Home and End, Enter on the focused row, a key inside a row's own control left alone, a shrinking filter not leaving focus past the end, an empty table not throwing) and `ConsoleNav` plus `AccessDenied` (list semantics, `aria-current`, a section a role cannot open rendering as text rather than a link, the refusal carrying the page's `h1`, restoring as a status rather than an alert).
- customer-web, 9 new tests beside the 4 existing copy-parity ones: `useMe` (a failed load fills nothing in, a 401 goes to sign-in rather than an error, a write adopts the payload it returns without a second GET, a refusal shows the API's own words and leaves the account untouched) and `CaseRow` (an undecided case says so instead of inventing a cause).

**`npm run lint` now runs at all.** It could not before: no app had an ESLint config, so `next lint` prompted interactively and exited 1 for all three. One shared `frontend/.eslintrc.json` (`next/core-web-vitals` plus `plugin:jsx-a11y/recommended`) and `eslint apps packages`, because `next` is not resolvable at the workspace root.

It found 15 errors. None were in the console pages E2 rewrote; all 15 are fixed rather than suppressed, and three were real:

- **The money confirmation sheet in the chat was not a dialog.** A scrim div with a click handler wrapping a panel: no `role="dialog"`, no `aria-modal`, no focus trap, no Escape, no focus return. It is the tap that moves money and it was the one sheet a keyboard or screen-reader user could not work. It is now `@clarity/ui`'s `Dialog`, with `dismissOnBackdrop={false}` because a stray tap on the scrim must not dismiss a decision about a refund.
- **The chat's history drawer had no close button at all.** The only way out was a mouse click on the scrim. It now has dialog semantics, a focus trap, Escape and a close button.
- **`VoiceSheet` promised `aria-modal` and delivered neither Escape nor a trap.** Both wired.

Two were jsx-a11y false positives against correct ARIA, and are configured rather than coded around: a scrollable region needs `tabIndex={0}` (WCAG 2.1 SC 2.1.1), and a `tablist` is deliberately not a tab stop in the ARIA tabs pattern. Both carry the reason in the config.

**The four specs UI02 names.** `autopsy-foresight.spec.ts` is split into `autopsy.spec.ts` and `foresight.spec.ts`, which is what UI02 rows 1 to 3 ask for, and `desk-provenance.spec.ts` (row 4) and `desk-authorization.spec.ts` (row 5) are new. The old combined file was stale twice over: it asserted a "Statistical baseline vs persona swarm" heading C4 removed, and signed in as a role E2's nav fix no longer offers Foresight to.

**A `product` staff account.** C4 created `Role.PRODUCT` and gave it `foresight:run` and `foresight:scenario:draft` alone, and the synthetic directory had no member of it. The rehearsal path was therefore unreachable from a browser: nothing could click Rehearse. Added to `config/staff/synthetic-directory.json` (scrypt hashes only) and to the e2e sign-in map.

**A phone viewport project** in `playwright.config.ts` (Pixel 7), scoped to the three specs where layout at 393px decides whether the journey works: the chat dispute, sign-in, and the receipt verdict. The console is deliberately excluded: it is a desk tool whose tables do not reflow, and a test asserting otherwise would be asserting something nobody asked the product to do.

**CI runs both.** The `frontend` job gains `npm run lint` and `npm test` before the build.

## Why

The plan's E6: no component test framework existed for the apps, four UI02 specs were missing, there was no mobile project, and `npm run lint` and `npm test` were scripts no workflow invoked.

## Decisions made

- **One ESLint config at the workspace root, not one per app.** The three apps share every rule and three configs is three things to drift. It needs `next` as a root devDependency because `eslint-config-next` loads its parser through `next/dist/compiled/...`.
- **`autopsy-foresight.spec.ts` deleted rather than repaired.** UI02 names two files; keeping a third that covers both would leave two places to update. Note: a parallel branch (`fix/e2e-foresight-and-session-expiry`) edits that same file, so this will merge as a delete-versus-modify conflict. The split is the intended resolution.
- **Every lint error fixed, none disabled inline except one with a stated reason.** A suppression is how a gate stops meaning anything a week later.
- **The `product` account's step-up code is `step-up`**, matching the other synthetic accounts, so `signInOnDesk` needs no special case.

## Docs updated

- [x] This devlog
- [ ] MODULE.md: n/a (frontend, no module)
- [ ] CHANGELOG.md: n/a (no `/v1` change)
- [ ] `docs/walkthroughs/WT-13-staff-console.md`: needs the `product` / `product-clarity` account added to its sign-in table, and re-verifying with a date and commit once `make e2e` has been run

## Tests

- `npm run lint`: clean (was: could not run).
- `npm run typecheck`: clean in all five workspaces.
- `npm test -w @clarity/console`: 17 passed. `npm test -w @clarity/customer-web`: 4 + 9 passed. `npm test -w @clarity/ui`: 48 passed (E1's, unchanged).
- `npm run build -w @clarity/console`: 8 routes. `npm run build -w @clarity/customer-web`: 11 routes.
- **Not run: `make e2e`.** The new and rewritten specs are compiled and type-clean but have not been executed against a live stack. The suite needs four web servers and a seeded synthetic world; `ARCHITECTURE.md:133` records that it had reportedly never been run end to end before the CI job existed, and a first run of six new specs should be expected to need cleanup. This is the one piece of E6 that is written and unverified, and it is the next thing to do.

## Open issues / next step

1. Run `make e2e` and fix what the six new or rewritten specs find.
2. E3 (console i18n) is **not done** and was explicitly deferred: the console has no `t()` calls and the `@clarity/i18n` catalogues still carry only the 66 customer keys. The console's ARIA labels added in E2 are English-only as a result.
3. WT-13 re-verification, once the browser suite has run.

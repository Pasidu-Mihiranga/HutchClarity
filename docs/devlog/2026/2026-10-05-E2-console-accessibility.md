# 2026-10-05 - E2 - The console, navigable without a mouse

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga |
| Work package | Workstream E2 (enterprise UI plan) |
| PR / commit | feat/enterprise-ui |
| Units touched | frontend/apps/console, frontend/e2e |

Written by an AI coding agent (Claude Code) under AGENTS.md §12.

## What changed

- **Landmarks and a skip link.** `layout.tsx` puts a visually-hidden skip link first in the DOM and makes `<main>` the focusable skip target, so the header's navigation plus three sign-in fields are no longer in the way of every page. `header` and `main` are now the only two top-level landmarks.
- **The section nav is a list** with `aria-current="page"` on the active entry. A section the role cannot open is no longer a dead link with a `title`: it renders as text with a visually hidden reason.
- **Every panel is a named section.** All eight pages (`/`, `/desk`, `/insights`, `/autopsy`, `/foresight`, `/studio`, `/audit`, `/admin`) wrap their cards in `<section aria-labelledby>`, so the audit page's eight panels of dense evidence can be jumped between rather than read in order.
- **The audit trail is a keyboard-navigable grid.** New `lib/useRovingRows.ts`: one tab stop for the table, Up and Down to move a row, Home and End to the ends, Enter to recompute the focused record's hashes. Fifty records used to mean fifty tab stops.
- **Four confirmations are now dialogs**, which is what gives the keyboard path a focus trap, an Escape route and focus return: the desk's merchant block, the admin kill-switch flip, the audit alert disposition, and Policy Studio's activate and propose-reversal.
- **Buttons name what they act on.** Six changes meant six buttons called "Approve"; eight clusters meant eight called "Confirm". Each now carries its policy key, cluster label, switch key or record number in its accessible name.
- **Errors and statuses announce.** Error and success banners are `Alert` (so `role="alert"` or `role="status"`), the desk's case panel is a polite live region because the click is on the left and the answer appears on the right, and `AccessDenied` is announced and carries the page's `h1`.
- **Form fields are associated.** The sign-in bar, the trail filters, the autopsy note, the studio draft form and the foresight scenario picker use `htmlFor`/`id` or `Field` rather than wrapping text or an `aria-label` standing in for a label.
- **The axe suite covers the console.** `e2e/accessibility.spec.ts` gains 11 tests: every route, signed in as a role that actually holds the permission it checks, plus three with a dialog open.

## Why

The plan's E2: zero `aria-*`, zero `role=`, zero focus management across the console, and an axe suite that covered no console page. The console is the staff surface for money decisions, so "works only with a mouse and only if you can see it" is not a defensible position for it.

## Decisions made

- **The Foresight nav entry now gates on `foresight:read`, not `desk:queue:read`.** The page itself has gated on `foresight:read` since C4, so a supervisor was shown a link to a refusal. Only `cx_engineer` and `product` hold the permission, which is why the new axe test signs in as CX. This makes `e2e/autopsy-foresight.spec.ts` wrong in a second way (it already asserts a heading C4 removed); E6 rewrites it.
- **Row-level grid navigation, not cell-level.** The trail's only per-row action is Verify, so cells have nothing to navigate to. `role="grid"` is set on the table because focusable `<tr>` elements in a plain `table` are a structure a screen reader cannot interpret.
- **Drafting and attaching a replay do not confirm.** Only the transitions that change what a customer sees do. A confirmation on every click teaches people to dismiss them.
- **The remaining raw colour classes are gone.** The `slate`, `emerald`, `amber` and `rose` classes E1 left on console pages now resolve through tokens, so the console is ready for the dark theme E3 switches on.

## Docs updated

- [x] This devlog
- [ ] MODULE.md: n/a (frontend app, no module)
- [ ] CHANGELOG.md: n/a (no `/v1` change)
- [ ] Walkthrough: WT-13 is re-verified at the end of the workstream, once E3 has changed the same screens' copy

## Tests

- `tsc --noEmit` clean in all five workspaces; `npm run build -w @clarity/console` builds all 8 routes.
- `tsc --noEmit` clean on the e2e specs.
- Not run: `make e2e`. The browser suite needs four web servers and has reportedly never run end to end (`ARCHITECTURE.md:133`); E6 is where it gets executed and cleaned up.
- `npm run lint` is still unusable repo-wide: no app has an ESLint config, so `next lint` prompts interactively and exits 1. E6 fixes this and wires it into CI.

## Open issues / next step

E3 (console i18n) replaces the copy on these same pages, including the ARIA labels added here, and switches on the theme switcher E1 deferred to it.

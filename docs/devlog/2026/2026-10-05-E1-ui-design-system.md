# 2026-10-05 - E1 - A real design system for the three web apps

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga |
| Work package | Workstream E1 (enterprise UI plan) |
| PR / commit | feat/ui-design-system |
| Units touched | frontend/packages/ui, frontend/apps/{console,customer-web,verify} |

## What changed
- `@clarity/ui` now has a token layer (`tokens.css`: colour, spacing, radius, elevation, type, motion, light and dark) and a shared Tailwind preset.
- New components, all `forwardRef` with ARIA: Select, Textarea, Field, Spinner, Skeleton, Alert, EmptyState, ErrorState, Dialog (focus trap, Escape, focus return, scroll lock), Tooltip, Toast, Table, Tabs (roving tabindex), Pagination, ThemeProvider. Button, Card, Badge and Input were rebuilt on the tokens (Button gains `loading`, `size`, `pill`, `danger`).
- console and verify use the preset; the sky-to-orange CSS override hack in the console is gone.
- customer-web: `:root` variables are now aliases onto the tokens, every hard-coded hex in pages and components was mapped to a token (orb canvases and PWA manifest colours stay literal on purpose), and the login page uses `Field`, `Input`, `Button`, `Alert`.
- Vitest, jsdom and Testing Library added to `packages/ui` (dev-only, MIT).

## Why
Two unconnected visual languages (Tailwind slate in console and verify, inline styles with orange variables in customer-web) and four 90-line components. E2 to E4 need these components.

## Decisions made
- No Radix or other UI dependency: Dialog, Tabs, Tooltip are about 300 lines and avoid a licence review (I17).
- The preset remaps `slate` onto tokens so unmigrated console pages follow the theme. Dark is therefore available but not switched on anywhere: `ThemeProvider` defaults to light and no app renders the switcher yet (console gets it with E3 so its labels are translated). Some status colours on console pages (emerald, amber, rose) are still raw and will be tokenised as E2 and E3 touch each page.
- customer-web's `--radius-sm` (14px) was renamed `--radius-card-sm` because it collided with the token of the same name.
- Remaining inline styles in customer-web (about 230) are left for E4, which rewrites those pages.

## Docs updated
- [x] frontend/README.md (design system section)
- [ ] MODULE.md: n/a (frontend package)
- [ ] CHANGELOG.md: n/a (no /v1 change)

## Tests
- `npm test -w @clarity/ui`: 48 passed (29 token contrast and parity, 19 component behaviour).
- `tsc --noEmit` clean in ui, customer-web, console, verify; `npm run build` builds all three apps.
- Not run: Playwright (`make e2e`).

## Open issues / next step
E2 (console accessibility) builds on Dialog, Table and landmarks. E5 will widen `npm run typecheck` to the apps.

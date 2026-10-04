# 2026-10-04 - FE - Chat waiting state: thinking orb

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | R5 frontend (plan 21 §7), customer-web chat polish |
| PR / commit | branch `feat/fe-chat-thinking-orb`, no PR yet |
| Units touched | `frontend/apps/customer-web`, `frontend/packages/i18n` |

## What changed
- New `components/ui/thinking-orb.tsx`: a dotted sphere drawn on a canvas that assembles top down, spins and lights its dots with four light programs, under a status label that cross-fades with a shimmer and three pulsing dots.
- `ClarityMessageCard`: `ThinkingCard` (bouncing dots) and `ProgressCard` (step list) replaced by one `WaitingCard`. While thinking it cycles Thinking, Searching, Analyzing, Composing. During account checks the label is the real current step and the checklist stays below it.
- Styles and keyframes (`mo-*`) appended to `app/globals.css`; the unused `ccBounce` keyframe removed from `app/clarity/page.tsx`.
- Four `wait.*` keys added to the shared i18n catalogue in en, si and ta.
- New `e2e/thinking-orb.spec.ts`: holds the turn request so the waiting state can be asserted and audited with axe, then releases it and checks the real answer replaces the orb; a second test checks the Sinhala label.

## Why
Requested UI upgrade: the chat's waiting animation should use the "AI thinking orb and input" (MorphOrb) design.

## Decisions made
- Only the waiting part of the design is used. The original also morphs the input pill into the orb and the orb into a plain-text answer card; the chat keeps its own composer and its structured result cards (decision, evidence, confirm), so those phases do not fit and were not carried over.
- Not copied verbatim: the supplied snippet imports an `index.css` whose `mo-*` class styles were not provided (only keyframes), and the project is Tailwind 3 without shadcn. The component was adapted rather than added as unused code.
- Dots are Hutch orange (`#f26226`) instead of the original light grey, which is invisible on the white chat.
- One component serves both waiting kinds, so when "thinking" is replaced by "progress" in the same slot the orb stays mounted and does not assemble twice.
- No artificial minimum thinking time: the original waits at least 3.45 s; the chat shows the answer as soon as the backend gives it.
- Accessibility: canvas and visual label are `aria-hidden`; the label is announced through a polite `role="status"`. Shimmer never goes lighter than `--muted` (5.3:1). `prefers-reduced-motion` draws one still frame and stops CSS animation.
- No new dependency (I17). The design came from a pasted third-party snippet; its licence was not stated. **Confirm the snippet's licence before merging.**
- Sinhala and Tamil strings are not native-speaker reviewed (same gap as ARCHITECTURE §7 item 5).

## Docs updated
- [x] `frontend/README.md` (customer-web screens)
- [ ] MODULE.md: not applicable, the frontend apps are documented in `frontend/README.md`
- [ ] Walkthrough: no step changes; the waiting state looks different, the flow is the same
- [ ] CHANGELOG.md / contracts: no `/v1` or public surface change

## Tests
- `tsc --noEmit` on customer-web: clean.
- `npm run build` (all three apps): compiled successfully.
- i18n key parity en/si/ta: ok.
- Playwright, full suite against this branch (lite API on :8100): `19 passed`; new spec: `2 passed`.
- Visual check at 1100 and 390 px widths.

## Open issues / next step
- Optional: a short "Done" sweep before the answer appears would need the result held back briefly; not done, to keep the answer instant.

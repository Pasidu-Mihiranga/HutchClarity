# 2026-10-02 - Kodee-style Clarity chat UI

> **Merged 2026-10-02:** imported from the team's `main` into the `dev` branch; paths updated to the R1 layout (see `2026-10-02-R1-dev-merge.md`).

## Intent

Redesign the Clarity conversation surface on the legacy self-care app into a
full-page, Kodee-like chat UX without changing detectors or money paths.

## What changed

- Extracted `clarity-chat.js` / `clarity-chat.css`; `customer.js` is the shell.
- Immersive Clarity view (hide agent bar / tab bar), chat header, multiline composer.
- Welcome + large suggestion cards, categorized topic browser, thinking/progress.
- Investigation and related in-thread cards, confirm modal, Success + Trust Receipt.
- Follow-up `facts` context; New chat + `localStorage` history; en/si/ta chrome strings.
- Updated WT-01 for the new chat steps.

## Verification

- Dilani VAS path: welcome → ask → progress → InvestigationCard → confirm → Success + receipt.
- Language switch and New chat / History on the chat header.

# 2026-10-04 - WA01 - Correct pairing entrypoint

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | R4, WA01 (#59) |
| PR / commit | pending |
| Units touched | WhatsApp transport image |

## What changed

- Corrected the npm start and pairing scripts to use TypeScript's actual
  `dist/src` output paths.
- Made the image build assert that both runtime entrypoints exist.

## Why

The first private pairing attempt failed before contacting WhatsApp because
the npm script addressed `dist/pair.js`, which the compiler does not create.

## Decisions made

No design change. This is a packaging-path correction.

## Docs updated

- [x] Service package and devlog
- [ ] Other docs: no behavior or contract changed

## Tests

- Pairing attempt: failed safely with `MODULE_NOT_FOUND`; no auth state changed.
- `npm test`: 9 passed.
- WhatsApp production image: built; build asserted both entrypoint files.

## Open issues / next step

Build, deploy, and repeat operator pairing.

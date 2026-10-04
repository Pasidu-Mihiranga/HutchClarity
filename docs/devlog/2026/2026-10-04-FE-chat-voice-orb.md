# 2026-10-04 - FE - Chat voice input with a voice-powered orb

| Field | Value |
|---|---|
| Author(s) | KusalPabasara; agent: Claude Code (Claude Opus 5.5) wrote the change and this entry |
| Work package | R5 frontend (plan 21 §7), customer-web chat polish |
| PR / commit | branch `feat/fe-chat-thinking-orb`, no PR yet |
| Units touched | `frontend/apps/customer-web`, `frontend/packages/i18n` |

## What changed
- The composer's **Speak** button, which did nothing, now opens `components/VoiceSheet.tsx`: a bottom sheet (centred dialog on wide screens) with an opt-in notice, **Start speaking**, a live status, the transcript, and **Ask**, **Edit** or **Try again**.
- New `components/ui/voice-powered-orb.tsx`: a WebGL (`ogl`) orb that swirls with the microphone's loudness, adapted from the "voice powered orb" design.
- Speech becomes text through the browser's `SpeechRecognition`, in `en-US`, `si-LK` or `ta-LK` following the chat language. **Ask** sends the words through the normal `ask` path; **Edit** puts them in the message box.
- **Speak** is shown only where the browser has speech recognition, restyled as an orange-soft pill with a mic icon.
- Thinking orb (previous entry) themed further: lit dots deepen from `--orange` to `--orange-strong`.
- 15 `voice.*` keys in the shared i18n catalogue (en, si, ta). Voice sheet styles (`vo-*`) in `app/globals.css`.
- New `e2e/voice.spec.ts` (5 tests) with a stubbed speech service.

## Why
Requested UI upgrade: use the voice-powered orb design for the voice section, in the Hutch theme.

## Decisions made
- **Browser speech recognition, opt-in.** The product owner chose this over orb-only or a new backend STT endpoint. In Chrome and Safari the browser vendor (Google, Apple) processes the audio; Hutch and Clarity receive only text. This sits close to I13, so it is opt-in and disclosed: the sheet says where the audio goes before anything listens, listening starts only on a tap, and the customer sees and can edit the transcript before it is sent. The transcript is a hint like typed text (I2) and decides nothing. **REQUIRES HUTCH CONFIRMATION** before any real-customer use; a HUTCH-hosted STT behind the `stt` model role would remove the third party.
- The orb reads loudness only, in the browser; no audio is recorded, stored or sent by our code.
- Hutch theme: palette changed from purple and cyan to `--orange`, a light amber and peach `#f8b39a`. The original's dark core and straight-alpha blending turned the glow grey on a white page, so the context and blend now use premultiplied alpha.
- Fixed from the original: the microphone was opened from two effects (a second stream leaked on each toggle); `onVoiceDetected` fired every frame and now fires only on change; added reduced-motion (frozen swirl) and a CSS fallback when WebGL is unavailable.
- Not added: `@radix-ui/react-slot`, `class-variance-authority` and the shadcn `Button`. They were only for the demo's button; the chat already has Hutch-styled buttons.
- Dependency (I17): `ogl` 1.0.11, licence **Unlicense** (OSI approved), no transitive dependencies. The design snippet's own licence was not stated; **confirm before merging**, as for the thinking orb.
- Sinhala and Tamil strings are not native-speaker reviewed (ARCHITECTURE §7 item 5).

## Docs updated
- [x] `frontend/README.md` (customer-web screens)
- [ ] Walkthrough / demo script: voice is optional and not on a demo path yet
- [ ] CHANGELOG.md / contracts: no `/v1` or public surface change

## Tests
- `tsc --noEmit` on customer-web: clean. `npm run build` (all three apps): compiled successfully.
- i18n key parity en/si/ta: ok.
- Playwright, full suite against this branch (lite API on :8100): `26 passed`.
- Visual check at 390 px with Chromium's fake microphone and SwiftShader WebGL.

## Open issues / next step
- Real-device check on Android Chrome and iOS Safari: language support for `si-LK` and `ta-LK` varies by device, and an unsupported language surfaces as the "not available" message.
- A HUTCH-hosted speech-to-text path (the `stt` model role) to replace the browser vendor's service.

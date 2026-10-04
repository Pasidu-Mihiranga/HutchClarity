# Hutch Clarity frontend

Lean npm workspaces monorepo for Phase **B5 / D2–D4 / D7**.

## Layout

```
frontend/
  package.json          # workspaces: packages/*, apps/*
  packages/
    ui/                 # @clarity/ui - design tokens (light/dark) + accessible components, tested with Vitest
    sdk/                # @clarity/sdk - ClarityClient → NEXT_PUBLIC_API_BASE
    i18n/               # @clarity/i18n - en / si / ta + t(lang, key)
    widget/             # @clarity/widget - <clarity-why-card> custom element
  apps/
    customer-web/       # Next.js 14 customer PWA (port 3000)
    console/            # Staff console: desk / insights / studio / admin (3001)
    verify/             # Public receipt verify /r/[id] (3002)
```

## Prerequisites

- Node.js 18+
- Backend API reachable (default `http://localhost:8000`): `make dev` from the
  repository root. These apps are the only UI, so the API serves no pages
  (FE01 retired the static UI it used to carry).

## Install & build

```bash
cd frontend
npm install
npm run build
```

All three apps emit Next.js standalone output. The generic production image is
`deploy/docker/Dockerfile.frontend`; it selects a workspace with `APP` and runs
as a non-root user behind the VPS same-origin reverse proxy.

## Develop

Set the API base once (or per shell):

```bash
export NEXT_PUBLIC_API_BASE=http://localhost:8000
```

| App | Command | URL |
|---|---|---|
| Customer web | `npm run dev:customer` | http://localhost:3000 |
| Console | `npm run dev:console` | http://localhost:3001 |
| Verify | `npm run dev:verify` | http://localhost:3002 |

Or from an app folder:

```bash
npm run dev -w @clarity/customer-web
```

## Screens (placeholders)

**customer-web**

- `/` - why balance changed + Why widget + language switcher (si/ta/en)
- `/login` - OTP request / verify via SDK
- `/case/[id]` - case detail
- `/receipt/[id]` - receipt view
- `app/manifest.ts` - PWA basics
- `/clarity` waiting state - `components/ui/thinking-orb.tsx`: dotted canvas orb with rotating, localised status labels while a turn is pending, and the real check steps during account checks (`e2e/thinking-orb.spec.ts`)
- `/clarity` voice input - **Speak** opens `components/VoiceSheet.tsx`: an opt-in sheet with the WebGL `components/ui/voice-powered-orb.tsx` (reacts to mic loudness, read locally), browser speech recognition in en/si/ta, and a transcript the customer checks before **Ask** or **Edit**. Hidden where the browser has no speech recognition (`e2e/voice.spec.ts`)

**console**

- Bottom **role switcher** (agent … security_admin) + step-up MFA toggle
- `/` - home with permission-aware section cards
- `/desk` - live queue + cockpit + approve (via `@clarity/sdk`)
- `/insights` - `/v1/demo/ops` summary
- `/autopsy` - DATA01-backed Complaint Autopsy reviewer workspace
- `/foresight` - synthetic baseline-vs-swarm scenario rehearsal workspace
- `/studio` - role-aware draft / publish stub / regulator export stub
- `/admin` - kill switches (`/v1/admin/switches`)

Walkthrough: [docs/walkthroughs/WT-02-staff-console.md](../docs/walkthroughs/WT-13-staff-console.md)

**verify**

- `/r/[id]` - fetches `GET /v1/verify/{id}`; falls back to a local valid/invalid demo when the API is down (ids containing `bad` → invalid)

## Packages

Shared packages are consumed via workspace `*` deps and `transpilePackages` in each Next.js app (source is TypeScript; no separate package build step required for local dev).

## Notes

- UI uses Tailwind class strings; each app includes Tailwind/PostCSS.
- OTP and case/receipt screens degrade gracefully with placeholders when the API is offline so UI can be reviewed without a live backend.

## Design system (`@clarity/ui`)

One token layer and one component set serve all three apps (plan workstream E1).

- **Tokens**: `packages/ui/src/tokens.css` defines colour (as RGB channels), spacing, radius, elevation, type and motion, with a light and a dark theme. Dark applies from `data-theme="dark"` on `<html>` or, when no theme was chosen, from the system preference. Every text-on-surface pair is contrast-tested (WCAG AA) in `packages/ui/test/tokens.test.ts`.
- **Apps wire it** by importing `@clarity/ui/tokens.css` in the root layout and adding `presets: [require("@clarity/ui/tailwind-preset")]` to `tailwind.config.js`. Use semantic classes (`bg-surface`, `text-fg-muted`, `border-border`, `bg-primary`), never a literal colour. The preset also maps the legacy `slate` scale onto the tokens so older pages follow the theme while they are migrated.
- **Components** (all `forwardRef`, ARIA wired): `Button`, `Card`, `Badge`, `Input`, `Textarea`, `Select`, `Field`, `Spinner`, `Skeleton`, `Alert`, `EmptyState`, `ErrorState`, `Dialog`, `Tooltip`, `ToastProvider`/`useToast`, `Table*`, `Tabs`/`TabList`/`Tab`/`TabPanel`, `Pagination`, `ThemeProvider`/`ThemeSwitcher`. Strings a component renders (close, dismiss, page labels) are props so the host app translates them.
- **Tests**: `npm test -w @clarity/ui` (Vitest, jsdom, Testing Library) covers focus trapping, keyboard behaviour, roles and token contrast.

# Hutch Clarity frontend

Lean npm workspaces monorepo for Phase **B5 / D2–D4 / D7**.

## Layout

```
frontend/
  package.json          # workspaces: packages/*, apps/*
  packages/
    ui/                 # @clarity/ui — Button, Card, Badge, Input
    sdk/                # @clarity/sdk — ClarityClient → NEXT_PUBLIC_API_BASE
    i18n/               # @clarity/i18n — en / si / ta + t(lang, key)
    widget/             # @clarity/widget — <clarity-why-card> custom element
  apps/
    customer-web/       # Next.js 14 customer PWA (port 3000)
    console/            # Staff console: desk / insights / studio / admin (3001)
    verify/             # Public receipt verify /r/[id] (3002)
```

## Prerequisites

- Node.js 18+
- Backend API reachable (default `http://localhost:8000`)

## Install & build

```bash
cd frontend
npm install
npm run build
```

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

- `/` — why balance changed + Why widget + language switcher (si/ta/en)
- `/login` — OTP request / verify via SDK
- `/case/[id]` — case detail
- `/receipt/[id]` — receipt view
- `app/manifest.ts` — PWA basics

**console**

- Bottom **role switcher** (agent … security_admin) + step-up MFA toggle
- `/` — home with permission-aware section cards
- `/desk` — live queue + cockpit + approve (via `@clarity/sdk`)
- `/insights` — `/v1/demo/ops`, autopsy, foresight
- `/studio` — role-aware draft / publish stub / regulator export stub
- `/admin` — kill switches (`/v1/admin/switches`)

Walkthrough: [docs/walkthroughs/WT-02-staff-console.md](../docs/walkthroughs/WT-02-staff-console.md)

**verify**

- `/r/[id]` — fetches `GET /v1/verify/{id}`; falls back to a local valid/invalid demo when the API is down (ids containing `bad` → invalid)

## Packages

Shared packages are consumed via workspace `*` deps and `transpilePackages` in each Next.js app (source is TypeScript; no separate package build step required for local dev).

## Notes

- UI uses Tailwind class strings; each app includes Tailwind/PostCSS.
- OTP and case/receipt screens degrade gracefully with placeholders when the API is offline so UI can be reviewed without a live backend.

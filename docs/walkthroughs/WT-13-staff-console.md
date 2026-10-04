# WT-02 - Staff console roles

> **Merged 2026-10-02:** imported from the team's `main` into the `dev` branch; paths updated to the R1 layout (see `2026-10-02-R1-dev-merge.md`).

| Field | Value |
|---|---|
| Audience | developers / demo presenters / judges |
| Journey | Staff password sign-in; Desk approve; Autopsy and Foresight; kill switches |
| Status | verified |
| Last verified | 2026-10-04 (local directory sign-in; VPS image is a root-side build, not a GitHub release) |

## 1. What you will see

The Clarity **console** (`:3001`) signs staff in with a username and password.
`POST /v1/auth/staff/login` reads the staff directory and assigns that
account's role. The browser cannot pick a role. When the directory is set,
`POST /v1/auth/staff/session` answers 404. Navigation and screens follow real
permissions from `/v1/auth/me`. The console **is** the Desk now: FE01
retired the static `desk.html` that used to serve `/desk`, `/ops`, `/autopsy`
and `/foresight`. Admin kill switches call `/v1/admin/switches`. The visual
language follows the IgniteX site (white, ink, orange). Records stay synthetic.

## 2. Prerequisites

The hosted synthetic demo is available at
`https://116.203.101.73:8443/`. Its `/v1` calls are same-origin through the
reverse proxy. For local development:

```bash
make dev                 # API on :8000
make web-install         # once
make web-console         # http://localhost:3001
```

`NEXT_PUBLIC_API_BASE` defaults to `http://localhost:8000`; export it only if
the API runs elsewhere. There is no static Desk to fall back to any more.

## 3. Steps

| # | You do | UI / channel | API call | What to check |
|---|---|---|---|---|
| 1 | Sign in as `agent` / `agent-clarity` | Header form | `POST /v1/auth/staff/login` | Subject `agent-1`; Desk + Insights enabled; Studio/Admin grey |
| 2 | Desk → open a waiting STAFF_APPROVAL case | Desk | queue + evaluate | Case panel shows cause and Approve as agent (may refuse above-cap) |
| 3 | Sign out. Sign in as `supervisor` / `supervisor-clarity` with step-up code `step-up`. Approve as supervisor | Desk | approve | Receipt issued; high-value needs the step-up code |
| 4 | Sign in as `platform` / `platform-clarity` with step-up, open Admin, turn off `auto_fix_global` | Admin | GET/POST `/v1/admin/switches` | Flip succeeds; history lists actor |
| 5 | Sign in as `auditor` / `auditor-clarity` | Nav | - | Desk/Insights denied (no `desk:queue:read`); honest AccessDenied |
| 6 | Sign in as `security` / `security-clarity` | Admin | GET switches | Can read switches; flip returns 403 (no `flags:kill_switch`) |
| 7 | Sign in as `vasops` / `vasops-clarity` with step-up → Suspend GameZone | Desk card | `POST /v1/admin/merchants/suspend` | Simulated block on Dilani |
| 8 | Sign in as `cx` / `cx-clarity` or `compliance` / `compliance-clarity` | Studio | local draft / export stub | Draft saves in sessionStorage; export downloads labelled JSON |
| 9 | As **supervisor**, open **Complaint Autopsy** | Autopsy | `GET /v1/demo/autopsy` | SYNTHETIC DATA, HYPOTHESIS labels, masked examples, trend and `TrigramSimilarity` disclosure |
| 10 | Open **Foresight** | Foresight | `GET /v1/demo/foresight` | SCENARIO, NOT CERTAINTY; baseline-vs-swarm bands; not calibrated warning |

## 4. Under the hood

- Local `make dev` loads `config/staff/synthetic-directory.json`. Those
  passwords are for the synthetic desk only. A deployment keeps its own file,
  mode 0600, and does not use this one. The hosted desk's accounts are not in
  the repo.
- Permissions and step-up checks are the production ones. The records are synthetic.
- Four-eyes: second approval must use a **different `user_ref`** (e.g.
  `sup-1` then `fin-1`), not the same person with two roles.
- Admins never hold money permissions even if stacked.

## 5. Troubleshooting

- CORS / network: confirm `NEXT_PUBLIC_API_BASE` and that `make dev` is up.
- The queue and the approval path are covered by `frontend/e2e/staff-desk.spec.ts`,
  so `make e2e` reproduces steps 1 to 4 without a browser of your own.
- Autopsy, Foresight and their denied role are covered by
  `frontend/e2e/autopsy-foresight.spec.ts`.
- Empty queue: cases appear after a customer opens one, or from cases already stored. There is no seed button.
- Flip refused: sign in again with the step-up code, then retry.
- Sign-in refused: the API on `:8000` must be started with `CLARITY_STAFF_DIRECTORY_FILE` (`make dev` sets it).

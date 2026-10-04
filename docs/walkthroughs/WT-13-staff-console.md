# WT-02 - Staff console roles

> **Merged 2026-10-02:** imported from the team's `main` into the `dev` branch; paths updated to the R1 layout (see `2026-10-02-R1-dev-merge.md`).

| Field | Value |
|---|---|
| Audience | developers / demo presenters / judges |
| Journey | Switch demo staff roles; Desk approve; Autopsy and Foresight; kill switches |
| Status | verified |
| Last verified | 2026-10-04 (browser suite and live VPS release `01d1762`) |

## 1. What you will see

The Clarity **console** (`:3001`) has a fixed bottom bar with every staff
role. One tap signs in through the simulated staff issuer
(`POST /v1/auth/staff/session`). Navigation and screens follow real
permissions from `/v1/auth/me`. The console **is** the Desk now: FE01
retired the static `desk.html` that used to serve `/desk`, `/ops`, `/autopsy`
and `/foresight`. Admin kill switches call `/v1/admin/switches`.

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
| 1 | Open console, tap **Agent** | Role bar | `POST /v1/auth/staff/session` | Subject `agent-1`; Desk + Insights enabled; Studio/Admin grey |
| 2 | Desk → Create demo cases → open a STAFF_APPROVAL case | Desk | cases + evaluate + queue | Cockpit shows cause and Approve as agent (may refuse above-cap) |
| 3 | Enable **Step-up MFA**, switch to **Supervisor**, Approve as supervisor | Desk | approve | Receipt issued; high-value needs step-up |
| 4 | Switch to **Platform**, open Admin, turn off `auto_fix_global` | Admin | GET/POST `/v1/admin/switches` | Flip succeeds; history lists actor |
| 5 | Switch to **Auditor** | Nav | - | Desk/Insights denied (no `desk:queue:read`); honest AccessDenied |
| 6 | Switch to **Security** | Admin | GET switches | Can read switches; flip returns 403 (no `flags:kill_switch`) |
| 7 | Switch to **VAS ops** + step-up → Suspend GameZone | Desk card | `POST /v1/admin/merchants/suspend` | Simulated block on Dilani |
| 8 | Switch to **CX eng** / **Compliance** | Studio | local draft / export stub | Draft saves in sessionStorage; export downloads labelled JSON |
| 9 | As **Supervisor**, open **Complaint Autopsy** | Autopsy | `GET /v1/demo/autopsy` | SYNTHETIC DATA, HYPOTHESIS labels, masked examples, trend and `TrigramSimilarity` disclosure |
| 10 | Open **Foresight** | Foresight | `GET /v1/demo/foresight` | SCENARIO, NOT CERTAINTY; baseline-vs-swarm bands; not calibrated warning |

## 4. Under the hood

- Roles are **asserted** for the demo (banner says so). Permissions and
  step-up checks are the production ones.
- Four-eyes: second approval must use a **different `user_ref`** (e.g.
  `sup-1` then `fin-1`), not the same person with two roles.
- Admins never hold money permissions even if stacked.

## 5. Troubleshooting

- CORS / network: confirm `NEXT_PUBLIC_API_BASE` and that `make dev` is up.
- The queue and the approval path are covered by `frontend/e2e/staff-desk.spec.ts`,
  so `make e2e` reproduces steps 1 to 4 without a browser of your own.
- Autopsy, Foresight and their denied role are covered by
  `frontend/e2e/autopsy-foresight.spec.ts`.
- Empty queue: Create demo cases while signed in as agent or supervisor.
- Flip refused: enable Step-up MFA, then retry.

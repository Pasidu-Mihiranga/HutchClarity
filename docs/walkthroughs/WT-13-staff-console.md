# WT-02 - Staff console roles

> **Merged 2026-10-02:** imported from the team's `main` into the `dev` branch; paths updated to the R1 layout (see `2026-10-02-R1-dev-merge.md`).

| Field | Value |
|---|---|
| Audience | developers / demo presenters / judges |
| Journey | Staff password sign-in; Desk approve; Autopsy and Foresight; kill switches |
| Status | verified |
| Last verified | 2026-10-04 (local directory sign-in; VPS image is a root-side build, not a GitHub release) |
| Re-verification owed | Steps 8-8b, 9-9b and 10-10b were rewritten for D3, D4 and C on 2026-10-05 and have **not** been walked in a browser since. The routes behind them are covered by acceptance tests; the click path is not. |

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
| 4a | Still on Admin, open **MCP Inspector**, press Open MCP Inspector | Admin | MCP Inspector deep-link to `clarity-mcp` | Inspector opens with Streamable HTTP URL; connect after `make mcp` + Inspector (WT-10) |
| 4b | Open **IAM**, pick a role, attach then detach a closed permission with a reason | IAM | `GET`/`POST /v1/admin/iam/roles*` | Effective matrix updates; money on admin roles refused (WT-13-admin-iam, ADR-0045) |
| 5 | Sign in as `auditor` / `auditor-clarity` | Nav | - | Desk/Insights denied (no `desk:queue:read`); honest AccessDenied |
| 6 | Sign in as `security` / `security-clarity` | Admin | GET switches | Can read switches; flip returns 403 (no `flags:kill_switch`) |
| 7 | Sign in as `vasops` / `vasops-clarity` with step-up → Suspend GameZone | Desk card | `POST /v1/admin/merchants/suspend` | Simulated block on Dilani |
| 8 | Sign in as `cx` / `cx-clarity`, open **Policy Studio**, open a change on an existing policy key | Studio | `GET`/`POST /v1/admin/policy/changes` | The change appears in `draft` with the class the artefact's tags give it |
| 8a | As **supervisor** (stepped up), approve that change, then schedule and activate it | Studio | `POST .../approve`, `.../schedule`, `.../activate` | State moves draft to active; the approval lists the approver, role and step-up |
| 8b | As **cx** again, try to approve a change you opened yourself | Studio | `POST .../approve` | Refused, and the page shows the API's own reason (maker-checker) |
| 9 | As **supervisor**, open **Complaint Autopsy** | Autopsy | `GET /v1/autopsy/clusters` | SYNTHETIC DATA, HYPOTHESIS labels, masked examples, trend and `TrigramSimilarity` disclosure |
| 9a | Confirm a cluster, then change the verdict with a reason | Autopsy | `POST .../review`, `.../supersede` | Both verdicts survive and are listed; a reversal with no reason is refused |
| 9b | Sign in as `agent` / `agent-clarity` and open Autopsy | Autopsy | `GET /v1/autopsy/clusters` | The workspace reads, and no verdict buttons appear (no `autopsy:review`) |
| 10 | Sign in as `product` / `product-clarity`, open **Foresight**, pick a scenario and press Rehearse | Foresight | `GET /v1/foresight/scenarios`, `POST /v1/foresight/runs` (202 + `Location`) | SCENARIO, NOT CERTAINTY; the run is stored and its report lists banded themes with a basis and caveats |
| 10a | Press Rehearse again | Foresight | `POST /v1/foresight/runs` | A new run, because the page mints a fresh `Idempotency-Key` per click. An repeated key returns the original run marked REPLAYED |
| 10b | Read the calibration panel | Foresight | `GET /v1/foresight/calibration` | NOT CALIBRATED comes from the API, not from the page. No launch decision rests on a rehearsal until it is backtested |

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

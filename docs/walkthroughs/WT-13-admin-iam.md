# Admin IAM role policies

| Field | Value |
|---|---|
| Audience | platform admins / developers |
| Surfaces | Console IAM tab · `/v1/admin/iam/*` |
| Related | [ADR-0045](../adr/0045-role-permission-overrides-on-static-baseline.md), [WT-13](WT-13-staff-console.md), plan 18 §5.4 |

## What the IAM tab shows

The **IAM** section (sidebar, gated on `iam:role:manage`) lists every closed
staff role and its effective permissions. For a selected role you can:

- see baseline vs attached vs detached
- **Attach** a closed permission that is not already effective (illegal options
  are hidden: locked permissions, money on admin roles)
- **Detach** an effective permission that is not locked

Every attach or detach asks for a reason and sends an `Idempotency-Key`. The
API refuses SoD breaks even if a client invents the call.

## Prerequisites

```bash
make dev                 # API on :8000
make web-console         # http://localhost:3001
```

Sign in as `platform` / `platform-clarity` (or `admin` / the directory password
for `platform_admin`). The IAM tab appears only when `/v1/auth/me` includes
`iam:role:manage`.

## Steps

| # | You do | UI / channel | API call | What to check |
|---|---|---|---|---|
| 1 | Sign in as platform admin, open **IAM** | Console IAM | `GET /v1/admin/iam/roles` | Matrix loads; roles list on the left |
| 2 | Select `agent`, attach a non-money permission that is not baseline (e.g. `merchant:suspend` if available) with a reason | IAM dialog | `POST /v1/admin/iam/roles/attach` | Effective list gains the permission; badge shows overrides |
| 3 | Detach that same permission with a reason | IAM dialog | `POST /v1/admin/iam/roles/detach` | Permission leaves effective (or stays in Detached if it was baseline) |
| 4 | Try to attach a money permission to `platform_admin` via API | curl / SDK | `POST .../attach` | 403 `ADMIN_MONEY_DENIED` |
| 5 | Sign in as `agent` and open `/iam` | Console | - | Redirect / AccessDenied (no `iam:role:manage`) |

## Invariants

- I9: routes declare `iam:role:manage`.
- I8: attach/detach are idempotent on `Idempotency-Key`.
- SoD: admins never gain money authority through this surface (ADR-0045).
- Policy Studio stays for business artefacts; this tab is who may call which API.

## Troubleshooting

- Tab missing: confirm the signed-in role holds `iam:role:manage` (`platform_admin`
  or `security_admin` on the synthetic directory).
- Attach list empty: every attachable permission is already effective, or SoD
  blocks the rest for that role.
- Unit coverage: `backend/tests/unit/test_role_policies.py`.

# 2026-10-05 - iam - local all-sections sign-in

| Field | Value |
|---|---|
| Author(s) | agent: Cursor |
| Work package | local desk sign-in |
| PR / commit | uncommitted |
| Units touched | iam (staff directory) |

## What changed
- A synthetic account may list `roles` as well as one `role`. Sign-in assigns that set. Existing accounts with one `role` are unchanged.
- `make dev` loads `config/staff/local-directory.json` when that file exists. The file is gitignored. E2E still loads the shared synthetic directory.

## Why
No single role opens every console section. A local sign-in can hold `product` and `platform_admin` together, which is the existing pair that opens Cases, Insights, Complaint Autopsy, Foresight, Studio, Audit, and Admin. The account is not in the shared directory.

## Decisions made
- No new role and no change to the permission matrix. Admin roles still cannot approve money, so this sign-in opens every section and still cannot approve a refund.
- The password stays in the gitignored file only.

## Docs updated
- [x] MODULE.md of: iam
- [ ] ARCHITECTURE.md / modules.md
- [ ] Walkthrough
- [ ] CHANGELOG.md / contracts
- [ ] Plan via CHANGES.md

## Tests
`tests/unit/test_staff_directory.py` for one role and for several roles. Login against the local API as the local account.

## Open issues / next step
None.

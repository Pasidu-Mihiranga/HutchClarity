# 2026-10-05 - D3 - Policy Studio on the governance API

| Field | Value |
|---|---|
| Author(s) | Pasidu-Mihiranga; agent: Claude Code |
| Work package | D3 (Workstream D, "Studio on the real governance API") |
| PR / commit | feat/console-studio-on-governance |
| Units touched | frontend/apps/console, frontend/packages/sdk |

## What changed

- `frontend/packages/sdk/src/client.ts` gains the seven governance calls that
  had no caller: `policyChanges`, `draftPolicyChange`, `reviewPolicyChange`,
  `approvePolicyChange`, `schedulePolicyChange`, `activatePolicyChange`,
  `rollbackPolicyChange`, with `PolicyApproval`, `PolicyImpact` and
  `PolicyChangeView` exported from the barrel.
- `frontend/apps/console/app/studio/page.tsx` rewritten onto those calls. The
  `sessionStorage` draft key and the `clarity-regulator-pack.json` blob
  download are gone, and so is the status line "Publish is not connected yet."
- The page now renders the real lifecycle: state badge, change class, approvals
  given against approvals needed, each approval with its approver, role and
  whether it was stepped up, the attached impact replay, the scheduled and
  activated timestamps.

## Why

Workstream D3. `/v1/admin/policy/changes` and its five lifecycle routes have
existed since M-GOV with no caller at all. The console page was shaped like a
policy tool and wrote to the browser, so no change a policy author made there
ever reached the maker-checker path, the change class or the audit trail. This
is wiring, not new behaviour: no backend file changed and the `/v1` contract is
untouched.

## Decisions made

- **No lifecycle logic in React.** The page does not compute which transition
  is legal, how many approvals are needed or whether this person may approve.
  It offers what the caller's permission allows and renders the refusal
  verbatim when the API says no. Those are money-path rules and a second copy
  in the browser is a second copy to get wrong.
- **Gate on `config:draft` and `config:approve` only.** The old page read
  `rule:draft`, `rule:publish` and `regulator_pack:export`. The routes check
  the config permissions, and `Role.COMPLIANCE` holds `rule:publish` without
  either config permission, so the old gate would have shown compliance a page
  where every call came back 403.
- **Review is a drafter's action, not an approver's.** `POST .../review`
  requires `CONFIG_DRAFT` server side, so the replay button sits with the
  drafter half of the page.
- **Say "propose reversal", not "roll back".** `governance.rollback` drafts a
  *new* change restoring the superseded version; it undoes nothing by itself
  and refuses a change that supersedes nothing. The button therefore appears
  only when `supersedes` is set, and its label says what it does.
- **`config:approve` is in `STEP_UP_PERMISSIONS`,** so an approver on an
  ordinary session is shown a re-authenticate prompt rather than four buttons
  that would all 403.

## Docs updated

- [x] CHANGELOG.md (SDK surface)
- [ ] MODULE.md: none. No module's public surface changed; this is a console
      and SDK change against routes that already existed.
- [ ] ARCHITECTURE.md / modules.md: not applicable, no new module or edge.
- [ ] Plan via CHANGES.md: not applicable, no plan chapter edited.
- [ ] Walkthrough: the Policy Studio flow has no walkthrough yet; D4 adds one.

## Tests

- `npx tsc -p packages/sdk/tsconfig.json --noEmit` - clean.
- `npm run build --workspace=apps/console` - 11/11 pages generated, `/studio`
  4.12 kB. The "Failed to patch lockfile" warning from Next is pre-existing on
  this workspace and does not fail the build.
- No backend test run for this entry: no backend file changed.

## Open issues / next step

- There is no component or e2e test for this page. Workstream E6 adds the
  frontend test framework; the Studio spec belongs there.
- `draftPolicyChange` sends the candidate value as the typed string from the
  form. A key whose artefact expects a number relies on the resolver's
  `_coerce`. A typed editor per artefact kind is worth doing when E1 lands the
  real form controls.
- D4 next: retire the demo routes the console no longer needs.

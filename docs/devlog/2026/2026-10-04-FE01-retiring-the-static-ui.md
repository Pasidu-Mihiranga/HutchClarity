# 2026-10-04 - FE01 - Retiring the static UI, and the verify page that faked a pass

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code |
| Work package | FE01 (#28), migration step R5 (docs/enterprise-plan/21) |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | interfaces.http, modules.receipts, integration.drivers.mock.store, frontend (all three apps, sdk), docs |

## What changed

- **The static UI is gone.** `interfaces/http/static/` is deleted and
  `_register_pages` with it, so the API serves `/v1`, the schema and the key
  endpoints and nothing else. Eight page routes were removed from the route
  contract's `PUBLIC` set.
- **Parity was proved before deleting anything.** The browser suite covered
  only customer-web, so `desk.html` and `verify.html` would have been retired
  on no evidence. Two spec files were added: `staff-desk.spec.ts` (the queue,
  and a four-eyes approval by a stepped-up supervisor on a case an agent
  raised, ending at a verified receipt) and `verify-receipt.spec.ts` (an issued
  receipt, a receipt that never existed, and an unreachable service). The
  Playwright config now starts the console on 3101 and the verify app on 3102
  alongside customer-web.
- **A real defect, found by writing those tests.** See *Decisions* below.
- **`VERIFY_BASE` moved to the verify app** (`http://localhost:3002/r`), since
  the `/v/{id}` route it named no longer exists. The mock store rebuilt a
  restored receipt's `verify_url` from a hard-coded `localhost:8000/v/...`; it
  now takes the configured base.
- **`make web`** runs all three apps at once, with no new dependency, because
  `make dev` alone no longer gives anyone a UI and the demo path needed a
  replacement.
- Next.js 16 is no longer FE01's scope: ADR-0031 records staying on 14, and
  FE02 carries the upgrade with the browser suite as its gate.
- Security headers: `/static/` left the cacheable list. The CSP's
  `style-src 'unsafe-inline'` stays, now for `/docs` and `/redoc` only, and the
  ZAP ignore for it says so instead of citing the static UI. Tightening it is
  its own change.

## Why

FE01 (#28) scope: "retire `interfaces/http/static` once parity is shown".
Parity had not been shown, which is why the retirement had not happened.

## Decisions made

- **The verify page was declaring unverified receipts valid.** It caught any
  failed API call and fell back to a "placeholder" verdict, and that verdict
  was *valid* for any id not containing the string "bad". Captured from the
  failing test against the old page, for `TR-2027-999999`, a receipt that was
  never issued, while the API answered `no such receipt`:

  ```yaml
  - heading "Verify receipt" [level=1]
  - text: Chain valid
  - paragraph: TR-2027-999999
  - paragraph: Credit applied · signature chain intact (placeholder)
  - term: Signature
  - definition: OK
  ```

  The static page it replaces showed an error on a 404. On the one page whose
  purpose is to let a stranger confirm a receipt is genuine, a fabricated pass
  is worse than no page, so the static UI could not be retired onto it as it
  stood. The page now has three outcomes and "could not check" is one of them;
  it is never a pass. `data.valid ?? data.chain_ok ?? true` became
  `data.valid === true` for the same reason. It also read `kid` where the API
  sends `key_id`, so the key id never rendered.
- **`ClarityApiError` in the SDK** rather than matching on message text: the
  page has to tell "this receipt does not exist" from "the service did not
  answer", and only one of those is a statement about a receipt.
- **The never-issued wording now matches DEMO_SCRIPT.md** ("No receipt
  numbered X has ever been issued"), which quotes it as a demo beat. The script
  was accurate about the static page and had become wrong.
- **No `/` route was added back.** A JSON index would be a new public surface
  nobody asked for; `/` is a 404 that still carries every security header, and
  the header tests assert exactly that.
- **No new dependency for `make web`.** `concurrently` would need a licence
  check (I17) to run three dev servers; shell job control does it.

## Docs updated

- [x] MODULE.md of: none. No module's public surface changed. `interfaces.http`
      and the frontend apps have no `MODULE.md`; `docs/modules.md` carries their
      rows and both were updated.
- [x] ARCHITECTURE.md / modules.md (front end row, `interfaces.http` row)
- [x] Walkthrough: WT-02 and WT-13, both re-verified against the browser suite
      and their "last verified" refreshed; `docs/WALKTHROUGHS.md` index rows
- [x] CHANGELOG.md / contracts: Removed, Changed and Fixed entries. The OpenAPI
      snapshot is unchanged, confirmed by `contracts-check`: every page route
      was `include_in_schema=False`.
- [x] Plan via CHANGES.md: v1.11, plan 19 §2.2 and the 21 §4 tree comment; plan
      README revision table
- [x] Also: README.md, frontend/README.md, DEMO.md, DEMO_SCRIPT.md,
      .env.example, docs/improvement-plan.md S3, .zap/rules.tsv, ci.yml comment,
      FE01 rewritten, FE02 added, ADR-0031 and its index row

## Tests

- `make check`: lint, `ruff format --check`, `mypy --strict` and the three
  import-linter contracts all pass ("Contracts: 3 kept, 0 broken").
  `pytest` reports **`1 failed, 1985 passed, 544 skipped in 64.62s`**, so
  `make check` exits non-zero here.
- **The one failure is this container, not this change.**
  `tests/unit/test_cassettes.py::test_an_outbound_connection_is_refused`
  expects the repository's own `LiveCallAttempted` guard to raise on an
  outbound call; this container routes outbound traffic through a proxy that
  answers `403 Forbidden` first, so httpx raises `ProxyError` instead.
  Verified by stashing every change in this devlog and running that test on the
  unmodified commit `e8da8a7`, where it fails identically. Nothing here touches
  that guard, and **CI is where `make check` green has to be confirmed.**
- The 544 skips are the `full`-profile parity suites, which need Docker.
- Browser suite: **14 passed** (9 existing, 5 new). The 9 existing had never
  been executed before: C05 wrote them and could not download a browser.
- `npm run build` for all three apps: exit 0, "Compiled successfully" three
  times. `npm run typecheck` (the SDK): exit 0.
- The two new verify tests were run against the *old* page first and failed,
  3 of 3, which is where the snapshot above comes from.
- One environment note, not a repo change: this container has Chromium 1194
  pre-installed while `@playwright/test` 1.63 wants 1243, and the matching
  build cannot be downloaded here, so the suite was run with a local-only
  config pointing `executablePath` at the installed binary. CI downloads the
  right build via `make e2e-install` and needs no such override.

## Open issues / next step

- **FE02**: the Next.js 16 upgrade, gated on the browser suite (ADR-0031).
- The si/ta native-speaker review is reported done and accepted by the
  maintainer (2026-10-04). No artefact of the review is in the repository; if
  one exists it is worth attaching to FE01.
- `style-src 'unsafe-inline'` can now be tightened, since the only pages left
  are `/docs` and `/redoc`. Those are already CSP-broken in a browser
  (`script-src 'self'` blocks their CDN bundle), which is a pre-existing
  condition this change did not touch and did not create.
- No GitHub issue has been opened for FE02; only the backlog file exists.

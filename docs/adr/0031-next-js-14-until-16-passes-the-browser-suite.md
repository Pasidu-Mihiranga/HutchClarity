# 0031 - Next.js 14 until 16 passes the browser suite

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Thanoj Buddhima |
| Plan references | enterprise-plan/19 §2.2, FE01 (#28), FE02 |

## Context

Plan 19 §2.2 names **Next.js 16** as the front end framework, and FE01 carried
"upgrade to Next.js 16" as scope. The three apps were built on Next.js 14.

The upgrade was attempted on 2026-10-04. Next.js 16.3.8 installs cleanly,
accepts React 18.2 (so it does not force a second major upgrade), passes
`tsc --noEmit`, and builds all three apps. On those signals it looks done.

It is not. Against the browser suite:

| Framework | Browser suite |
|---|---|
| Next.js 14.2.35 | **9 of 9 passing** |
| Next.js 16.3.8 | **2 of 9 passing** |

Adding `allowedDevOrigins`, which is the migration note Next itself prints for
the blocked `/_next/hmr` requests, changed which tests failed without reducing
how many.

Nothing in the failures pointed at a defect in our code. They are runtime
differences between the two majors that need their own investigation.

Those 9 passing tests on 14 are a measured result, not an assumption: the suite
had never been executed before FE01, because the environment that wrote it
could not download a browser. FE01 ran it, and the suite is now 14 tests.

## Decision

**Stay on Next.js 14 for now.** Plan 19 §2.2 records Next.js 14 as the current
framework with 16 as the target, and FE01 no longer carries the upgrade.

The upgrade is **FE02**, with the browser suite as its acceptance gate: it is
done when the suite passes on 16, not when the build compiles.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Ship Next.js 16 anyway, since it builds | A build that compiles is not an upgrade that works. The suite exists to catch this class of regression; overriding it on its first real finding would make it decorative. |
| Ship 16 and mark the failing tests as expected failures | That is deleting the evidence. Seven failures across the chat journey, the knowledge citation, the no-source handoff, sign-in and the accessibility audits are not a reporting problem. AGENTS.md §10 forbids it besides. |
| Force React 19 alongside 16 | Untested here, and a second major upgrade is a worse starting point for diagnosing the first, not a better one. |
| Keep 16 in plan 19 and leave FE01 open indefinitely | A plan the code knowingly contradicts is a plan nobody trusts. Recording what is true, with the reason, is what this record is for. |

## Consequences

- The three apps stay on `next@^14.2.35`; `frontend/package-lock.json` resolves
  14.2.35.
- Plan 19 §2.2 says Next.js 14 and points here. `ARCHITECTURE.md`,
  `docs/modules.md` and `docs/improvement-plan.md` S3 follow.
- Node 24 LTS is unaffected: Next 14 runs on it.
- FE01's remaining scope was the static UI retirement, which it completed; the
  framework upgrade is FE02.
- **Two traps for whoever retries it.** Next 16 rewrites `tsconfig.json` and
  `next-env.d.ts` in every app on install, so a revert has to restore those
  too. It also writes `AGENTS.md` and `CLAUDE.md` into `apps/customer-web/`:
  by the "closest file wins" rule in this repository's own `AGENTS.md`, agent
  instructions shipped by a dependency would outrank the project's rules for
  anyone working in that directory. They were deleted during the revert and
  must not be committed by accident.

## Compliance

The `frontend` CI job builds all three apps and the `e2e` job runs the browser
suite on every push. An upgrade to 16 is accepted when both stay green with no
test skipped or relaxed, and this ADR is **superseded** at that point rather
than edited.

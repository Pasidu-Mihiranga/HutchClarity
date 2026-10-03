# 2026-10-04 - D1 - Fix the double-tap state race

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) diagnosed, fixed and wrote this entry |
| Work package | B06 (issue #14), defect D1 |
| PR / commit | #14 |
| Units touched | modules/resolution |

## What changed

- `ResolutionService._execute` no longer advances the case to `EXECUTING` when
  execution has already begun. The new `_EXECUTION_BEGUN` set covers
  `EXECUTING`, `ACTIONED`, `RECEIPTED` and `COMPENSATING`.
- New regression test `test_d1_a_tap_that_confirms_before_the_winner_finishes_joins_it`,
  which forces the interleaving instead of racing for it.

## Why

CI failed on B06's own acceptance tests:

```
AssertionError: 1 of 1500 taps failed, first:
  [IllegalTransition('illegal case transition ACTIONED -> EXECUTING')]
```

A plan stays `PENDING` until `execute` runs, so two taps can both mint a
confirmation token: `confirm_by_customer` only refuses the second caller once
the first has actually executed. Both then reach `_execute`, which tested

```python
if record.case.state is not CaseState.EXECUTING:
    self._advance(record, CaseState.EXECUTING)
```

If the slower tap arrived before the faster one finished, the state was
`EXECUTING`, the advance was skipped, and everything worked. If it arrived
after, the state was `ACTIONED` or `RECEIPTED`, and the advance attempted
`ACTIONED -> EXECUTING`, which `CASE_TRANSITIONS` refuses.

**No money moved twice and no second receipt was issued.** The tool layer's
idempotency key and the receipt's plan index both held. The failure was that
one tap of a concurrent pair got an exception instead of the winner's receipt.

## Decisions made

1. **Widen the guard, do not catch the exception.** Catching
   `IllegalTransition` around the advance would hide real illegal transitions
   too. Naming the states in which execution has already begun says what is
   true, and any other illegal transition still raises.
2. **Skipping the advance is safe rather than lenient.** The idempotency key
   still makes the tool layer report the duplicate as a replay, so the caller
   takes the `result.replayed` path and joins the winner's receipt. The
   guarantee comes from the idempotency key, not from the state check.
3. **The regression test forces the interleaving.** The two existing threaded
   tests hit this on a two-core CI runner and never on a 14-core developer
   machine, and 400 local iterations of the two-thread version produced zero
   failures. A test that reproduces only on someone else's hardware is not a
   regression test. The new one patches `confirm_by_customer` so the winner
   waits until the loser has minted, and the loser waits until the winner has
   finished, which is the exact order CI hit.

## Docs updated

- [ ] MODULE.md - no public surface changed
- [ ] CHANGELOG.md - no contract change
- [x] This devlog entry

## Tests

```
deterministic repro before the fix   RECEIPTED -> EXECUTING, every run
deterministic repro after the fix    second execute: OK
make check                           1887 passed, 544 skipped
```

Non-vacuity: restoring the original `is not CaseState.EXECUTING` check fails
`test_d1_a_tap_that_confirms_before_the_winner_finishes_joins_it` on every run,
while the two threaded tests still pass locally. That is the whole point of
adding it.

## Open issues / next step

- **I closed #14 on a local run while CI was red.** Reopened. A green
  `make check` says nothing about tests whose outcome depends on core count and
  scheduling; for those the CI result is the authority.
- The two threaded tests are kept: they are what found this. But they are
  probabilistic, and the deterministic test is what will keep it fixed.

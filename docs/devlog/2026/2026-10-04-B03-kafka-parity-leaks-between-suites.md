# 2026-10-04 - B03 - Kafka parity leaks between suites

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) found and measured it |
| Work package | B03 (issue #11), observation only |
| PR / commit | none: nothing changed |
| Units touched | none |

## What was observed

Running the full profile's two suites in **one** pytest process fails three
Kafka parity tests:

```
pytest tests/contract tests/integration
  FAILED test_bus_parity.py::test_a_handler_that_fails_once_sees_the_event_again[kafka]
  FAILED test_bus_parity.py::test_a_blocked_event_clears_once_the_handler_recovers[kafka]
  FAILED test_bus_parity.py::test_every_group_gets_its_own_copy[kafka]
  3 failed, 1124 passed, 10 skipped
```

Running either suite on its own is clean:

```
pytest tests/contract                      1094 passed, 10 skipped
pytest tests/contract/test_bus_parity.py -k kafka    14 passed
```

## Why CI does not see it

`backend-full` runs them as two separate invocations:

```yaml
- name: Parity suites against the real drivers
  run: pytest tests/contract -v -ra
- name: Integration (schema isolation, row-level security, two replicas)
  run: pytest tests/integration -v -ra
```

So CI is structurally immune to this, and a developer running
`pytest tests/contract tests/integration` in one go is exercising a
combination CI never does. That is how it stayed unnoticed.

## What it is not

Not a regression. The changes between the last clean combined run and this one
were the HTTP security headers, the MCP health route, the replica walk order
and the workflow file. None of them touches Kafka, and `backend-full` has been
green on this code.

## What it probably is

Consumer-group and offset state surviving across tests inside one process. The
three that fail are the ones that depend on redelivery and per-group position:
a handler that fails once and sees the event again, a blocked event clearing,
and each group getting its own copy. All three are about *where a group is*,
which is exactly the state a previous test in the same process can leave
behind. The local broker had also been up for 32 hours across dozens of runs.

## Why nothing was changed

Diagnosing it properly means finding which earlier test leaves the state and
making the fixture clean up after itself, which is a focused piece of work on
B03's parity suite rather than something to bolt onto an unrelated change. The
honest position is that it is recorded and reproducible rather than quietly
written off as "flaky".

## Next step

- Reproduce with `-p no:randomly` and bisect the suite to find the test that
  leaves the group state.
- Consider a unique consumer group per test, which would make the suite
  independent of what ran before it.
- Until then, a developer seeing these three fail should re-run the two suites
  separately before assuming a real defect.

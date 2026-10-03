# 2026-10-04 - B10 - Get the CI lanes green

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus) diagnosed, fixed and wrote this entry |
| Work package | B10 (issue #18) |
| PR / commit | #18 |
| Units touched | .github/workflows, platform/messaging/drivers, backend/scripts, frontend lock file |

## What changed

Five of six CI jobs were failing on every push, for four unrelated reasons.
`make check` was green the whole time, which is why nobody noticed.

1. **mypy, lite lane.** `kafka.py:474: Returning Any from function declared to
   return "bytes"`. `confluent_kafka` is an optional extra that ships no stubs,
   so the lite lane (`pip install -e ".[dev]"`) resolves everything it returns
   to `Any`, while a developer machine with the `kafka` extra installed sees a
   real type and reports nothing. `_body` now narrows the payload with
   `isinstance` and refuses a non-`bytes` value the same way it already refused
   a null one.
2. **`npm ci`, frontend and contracts lanes.** `package-lock.json` was missing
   `@playwright/test`, `playwright` and `playwright-core` at 1.63.0, so
   `npm ci` refused to run and both jobs died at Install. Synced with
   `npm install --package-lock-only`: three packages added, nothing else moved.
3. **Licence gate, sbom lane.** `protobuf (7.36.2): '3-Clause BSD License' is
   not on the allowed list`. That is BSD-3-Clause spelled the other way round.
   The gate was stopping the build on wording, not on a licensing problem. Both
   classifier spellings added.
4. **OPA service container, full lane.** `Exit code 125 returned from process
   '/usr/bin/docker'` at Initialize containers. A GitHub service container
   cannot set the image's command, and OPA needs one (`run --server`), so the
   command had been smuggled in as `options: --args --server --addr=...`, which
   `docker create` rejects outright. OPA now starts as a `docker run` step with
   `config/opa` mounted, which is what `deploy/compose/full.yml` already does.

New `backend/tests/unit/test_licence_gate.py`: 23 tests over the gate in both
directions.

## Why

Issue #18 asks for CI lanes that fail when they should. Two of its own
acceptance tests are about the lanes catching defects, and a lane that cannot
start catches nothing. The issue could not honestly be closed with the workflow
in this state.

## Decisions made

1. **`isinstance`, not a `# type: ignore`.** `warn_unused_ignores` is on, so an
   ignore that silences the lite lane would itself fail the local run where the
   package is installed. The narrowing is correct in both configurations and is
   a real guarantee rather than a silenced warning.
2. **OPA moves to a step, mounting the policy.** The old comment said a service
   container cannot mount the workspace and therefore uploaded the policy
   through OPA's API. True, but it missed that a service container cannot set
   the command either, which is the actual failure. As a step it can do both,
   and it now loads the policy exactly as the local compose stack does, so the
   two stop drifting. The verification query that follows is kept: an OPA with
   no policy denies everything, which the parity suite would read as a
   disagreement with Python rather than as a policy that never loaded.
3. **The licence gate gets tests rather than just a new entry.** It runs only
   in the `sbom` job, so a break in it is invisible until a push fails. The
   tests pin refusals too (BSL, SSPL, AGPL, Commons Clause, Elastic, and an
   unknown licence), because a gate tested only for what it allows turns into a
   rubber stamp.
4. **The lock file is synced, not regenerated.** `--package-lock-only` adds the
   three missing packages and moves nothing else, so this commit is not also a
   silent dependency bump.

## Docs updated

- [ ] MODULE.md - no module surface changed
- [ ] CHANGELOG.md - no public surface or `/v1` change
- [x] This devlog entry

## Tests

```
make check                                        1886 passed, 544 skipped
full lane (contract + integration, live stack)    1127 passed, 10 skipped
mypy under a config that reproduces the lite lane Success: 238 source files
mypy with the kafka extra installed               Success: 238 source files
npm ci                                            exit 0
npm run build (three apps)                        exit 0
licence gate against the live dependency set      71 dependencies, all neutral
docker run of the exact new OPA step              creates, loads, answers true
```

Three non-vacuity probes on the licence gate:

| Probe | Test that failed |
|---|---|
| remove the `3-Clause BSD License` spelling | the parametrised case and the named regression test |
| allow anything not on the list | unknown-licence-stops-the-build |
| drop the refusal check | refusal-wins-over-a-dual-licence |

## Open issues / next step

- The lite lane and a developer machine do not install the same packages, which
  is how the mypy failure hid. Worth a `make check-lite` that installs only
  `[dev]`, or accepting that the lite lane is the authority and running it
  before pushing.
- Local full-stack ports differ from CI (PostgreSQL on 5440, OpenBao token
  `clarity-development-only`), so the full lane cannot be run locally by
  copying the workflow's env block. A `make test-full` target would fix that.
- `npm audit` reports advisories on the frontend tree. Not addressed here; it
  belongs to #42 (X01).

# 2026-10-04 - C5 (F07, F08) - two events, and a radar that only counts

| Field | Value |
|---|---|
| Author(s) | agent: Claude Code, for Pasidu Mihiranga |
| Work package | C5 (workstream C, plan items F07 and F08) |
| PR / commit | branch `feat/foresight-events-radar`, stacked on C2 |
| Units touched | contracts/events, foresight, platform/persistence (schema registry), app/collections, app/container, docs/enterprise-plan |

## What changed

- **`forecast.ready` and `spike.detected`** in `clarity.contracts.events`, with payload models, registry entries and sample payloads.
- **New `radar.py`:** `ComplaintRadar` consumes `complaint.created`, counts per channel in a fixed window, and raises a `DetectedSpike` when a window reaches a multiple of the trailing average. Plus `ComplaintObservation` and an eighth collection, `foresight.observations`.
- **`service.py`:** a finished run publishes `forecast.ready` through the outbox in the same transaction as the report (I7).
- **Four new policy keys** for the radar: window, baseline windows, threshold multiple and floor.
- **`app/container.py`:** builds the radar and registers it as a `complaint.created` consumer in its own group.
- **Plan 21 §11.3**: `forecast.ready` and `spike.detected` rows added, and `complaint.created` now records the radar as a second consumer. Plus `CHANGES.md`.

## Why

Plan C5. Two plan bugs are named in it and both are fixed here:

- **18 §159 promises both events while 21 §11.3 omits foresight entirely.** 21 is operative (ADR-0029 names it, `test_event_contracts.py` enforces it), so both rows are added. That test now fails if the table and the code disagree, which is how it was caught.
- **The `_FORBIDDEN_SEGMENTS` trap.** The plan flags that `scenario_name` and `migration_card_count` are "literally uninstantiable" because the base class rejects any field whose `_`-separated segments hit `name` or `card`. That is exactly right, and I verified it rather than taking it on trust: both raise `TypeError` at class definition time. A parametrised test pins it.

## Decisions made

- **Channel scope only, and it is a consequence rather than a preference.** `complaint.created` carries a complaint id, a channel, a language and an optional case id. No cluster. A cluster-scoped spike would need a field that does not exist, and inferring one in the consumer would be guessing at which complaints belong together. `SpikeScope` is an enum with one member so a second scope is an addition, not a reshape.
- **An eighth collection.** The plan listed seven and did not account for the radar needing somewhere to count. `foresight.observations` is append-only and keyed by event id, which is both the idempotency mechanism (I7) and the reason it cannot be rewritten: the only way to make a spike disappear would be to delete some of the observations that raised it. It mirrors `proactive.signals` exactly.
- **The radar counts, it does not read.** `ComplaintObservation` keeps an event id, a channel code and a time. A test asserts those are its only three fields. `autopsy` is what reads what people said; the two consume the same event and share nothing.
- **A fixed window grid from the epoch, not a trailing window.** A trailing window would give each replica its own boundaries and its own spike id. Snapping to a grid means two replicas seeing the same complaint derive the same id, so one window raises one spike.
- **A floor under the threshold.** Without it a quiet channel going from one complaint to three is a tripling, which is true and useless.
- **Empty baseline windows count towards the average.** Dropping them would average over only the busy hours and make the baseline look like the peak rather than the usual.
- **Not enough history means no spike.** The first busy hour with nothing behind it is a statement about the radar's age, not about traffic.

### A real inconsistency the tests found

My first version raised a spike whenever the baseline was zero, because `observed < 0 * threshold` is always false. But `DetectedSpike.ratio` already answered `None` for a zero baseline with the comment that "a window with nothing to compare against" is not "infinitely bad". The detector and the record disagreed.

Resolved in favour of raising it: "this channel was quiet and now it is not" is the signal a radar exists for, and suppressing it would be worse. But the spike now carries a caveat saying it rests on the floor alone and that no multiple of normal could be computed, so a reader is not left to infer a ratio from a `None`. The test that caught it asserts all three: the baseline, the `None` ratio and the caveat.

## Docs updated

- [x] `MODULE.md` of: foresight (files, used-by, an events table, the data-owned table with the eighth collection, invariants, tests, history)
- [x] This devlog
- [x] `CHANGELOG.md`
- [x] **New events**: producer contracts in `clarity.contracts.events`, plan 21 §11.3 rows, sample payloads in `tests/support/events.py`
- [x] **Plan**: `docs/enterprise-plan/CHANGES.md` entry alongside C4's
- [ ] `docs/modules.md` / `ARCHITECTURE.md`: not needed. Foresight remains a leaf; consuming an event is not a synchronous dependency (ADR-0029: calls for answers, events for side effects).
- [ ] ADR: none. The radar follows the existing consumer pattern (`proactive`) rather than introducing one.
- [ ] Walkthrough: not needed yet. `GET /v1/foresight/spikes` (C4) is what will surface these; no console screen reads it.

## Tests

- `tests/unit/test_foresight_radar.py`: **32 new tests**. What a spike is, what it is not (the quiet-channel tripling, the under-threshold busy window, the first busy hour, partial history), idempotency on replay, per-channel separation, codes-only shape, the four policy inputs, both events through the outbox, and the two uninstantiable field names.
- `tests/contract/test_event_contracts.py`: now covers both new events; it reads plan 21 §11.3 and fails if the table and the code disagree.
- `make check`: **2713 passed, 640 skipped** (2681 on C2's branch), ruff, mypy --strict over 250 files, import contracts 3 kept 0 broken.
- **Against a real PostgreSQL 16**: `foresight.observations` is created in `clarity_foresight` and holds `INSERT`, `SELECT` and nothing else, read back from `information_schema`.

## Open issues / next step

- The radar scans every observation for a channel on each event. That is fine at prototype volumes and matches `proactive`, but it is linear in history, and the observations are append-only so history only grows. A real deployment wants either a windowed index or a periodic compaction into per-window counts; the detection logic would not change.
- `spike.detected` has no consumer yet. Plan 21 §11.3 lists the console and alerts; neither reads it.
- Cluster-scoped spikes wait on a published event that carries a cluster.
- `forecast.ready` is published but nothing consumes it either; the Foresight console page is D-workstream work.

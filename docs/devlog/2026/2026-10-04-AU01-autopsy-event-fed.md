# 2026-10-04 - AU01 - Autopsy: event-fed, reviewed, and labelled

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | AU01 (`docs/backlog/issues/AU01-autopsy-event-fed-embeddings-via-the-embed-role.md`, #13), Wave 4 |
| PR / commit | not committed at time of writing |
| Units touched | `modules.autopsy` (`review.py`, `repository.py`, `service.py` new; `pipeline.py`), `app` (`container`, `collections`), `interfaces.http` |

## What changed

- **`review.py`**: the review workflow. `ClusterReview` as an immutable record,
  `ClusterReviews.record` and `.supersede`, and `staff_view`, which is the only
  sanctioned way to put a cluster in front of a person.
- **`repository.py`**: `autopsy.complaints` and `autopsy.clusters`, so a
  verdict survives the request that gave it.
- **`service.py`**: `AutopsyService`, consuming `complaint.created` and
  redrawing clusters on `rerun`.
- **`pipeline.py`**: a `Similarity` seam, `recluster` for already-masked
  complaints, and `ComplaintAutopsy.confirm` removed.
- `GET /v1/demo/autopsy` served by the service; the consumer registered in the
  container as the `autopsy` group.

## The review workflow was a review workflow in name

What was there:

```python
cluster.status = ClusterStatus.CONFIRMED if accept else ClusterStatus.REJECTED
cluster.label = f"{cluster.label} (reviewed by {reviewer})"
```

Four problems in two lines. It wrote audit data into a **display string**. It
appended twice if it ran twice. It kept no time and no note, so there was
nothing to look up and nothing to ask about later. And it had nowhere to
persist to: the cluster lived in a report object built per request, so a
verdict was lost the moment it was given.

AU01's title is "review workflow", so this is the substance of it. A verdict is
now its own immutable record with a reviewer, a time and a note; the label is
display text and a review never writes to it; and the cluster and its review
history are stored.

Two rules follow from treating a verdict as evidence rather than a flag:

- **A second verdict is refused.** It would overwrite somebody's professional
  judgement with no trace of the first. Changing one takes `supersede`, which
  keeps both and links them.
- **Superseding requires a reason**, where a first review's note is optional.
  Reversing a colleague's decision is the case where the reason matters most,
  and an unexplained reversal is exactly what an auditor will ask about.

## Acceptance 1 is about the screen, not the enum

"An unreviewed cluster shown to staff is labelled as a hypothesis." The status
enum already existed and `test_clusters_start_as_hypotheses` already asserted
it. What did not exist was any guarantee about what reaches a person.

A cluster is a machine's guess that forty complaints share one cause. Labelled
as a hypothesis it is useful to a CX engineer; unlabelled it is a finding
nobody established, which I16 forbids. The status being right while the screen
says nothing about it is precisely the failure mode, so the test asserts the
staff-facing representation and not the enum.

`staff_view` is therefore the only sanctioned representation, and it always
carries `hypothesis`, `status_label` and `acted_on`. A caller assembling a dict
by hand could forget one; there is one function so there is one thing to get
right.

Two smaller labelling decisions:

- **`suggested_rule_id` travels with `suggested_rule_is_a_guess`.** A rule id
  beside a cluster reads as "this is caused by that", and on an unreviewed
  cluster nothing has established it. Dropping the id instead would remove the
  one thing a reviewer most wants to see.
- **`acted_on` is always false**, and confirmed says "not yet a published
  rule". Confirmed means a person agreed, not that anything changed: turning a
  cause into a rule goes through the policy lifecycle (plan 20). A surface that
  implied the loop had closed would be the same error one level up.

## The event carries no text, and that shaped the design

`ComplaintCreatedV1` holds a `complaint_id`, a channel, a language and a case
id. **No text.** That looked at first like a gap, and it is not: putting a
customer's words in the message bus copies complaint content somewhere nobody
owns its retention, which is the same reason `conversation.turn.completed`
carries no message text and `knowledge.published` carries no clause text.

So the consumer is a notification handler rather than a data handler. It takes
the id and fetches the text through a `ComplaintSource` seam the composition
root fills, and nothing in the module reaches for a store it does not own (I6).
A test asserts the event still has no `text` field, because the day somebody
adds one is the day autopsy starts storing bus content.

Two consequences worth stating:

- **Clustering happens on a re-run, not per complaint.** One complaint is not a
  cluster and cannot be: a cluster is a claim that several share a cause, so
  one arriving changes the answer for all of them. The consumer masks and keeps
  each as it arrives; `rerun` redraws over everything kept. That makes the
  serverless batch job and the event feed the same code path rather than two
  implementations that drift into two answers for one corpus.
- **A re-run keeps reviewed clusters and replaces unreviewed ones.** It may not
  discard a recorded judgement, and leaving the old hypotheses would show a
  reviewer two overlapping guesses about the same complaints.

**Nothing produces `complaint.created` yet.** The producer is the channels work
(W4, plan 21 section 11.3 lists it as "channels / case"), which is not built,
so the consumer is wired and idle. That is the right half to build first: the
issue's scope says consume, and a consumer tested against a real event is
verifiable today where a producer would need a channel.

## The embed role, again

Issue #13 and plan 02 section 3.3 both say embeddings through the AI gateway.
**There is no embedding model in the system**, for the third work package in a
row: `ModelRole.EMBED` is a declared role name with no implementation,
`local-bge` is bound to `TemplateProvider` as a stand-in, and
`RoleRouter.invoke` returns `str`, which cannot carry a vector. K02 and K03 hit
the same wall.

So `Similarity` is a protocol, `TrigramSimilarity` is the deterministic
default, and it is **named for what it is** rather than for what it stands in
for, so nobody reads a cluster as semantically grouped. An embedding-backed
measure drops in without touching the clustering.

Worth being precise about what is carrying the load today: the pipeline
canonicalises each complaint to a short English form **before** comparing, so
Sinhala, Tamil and Singlish complaints about one thing meet. That
canonicalisation is doing the job embeddings would do, by a keyword table, and
it only covers the phrases in the table. Trigram cosine then splits whatever
the table left as "unclassified". So the multilingual clustering the deck
describes is real for known phrases and absent for everything else, and an
embedding model is what would close that.

## Two things found while building

**A lint error that was a logic bug.** The demo route iterated the seeded
complaint texts and then called `accept(f"demo-{index}")`, which fetches text
from the *source*. The texts were never used, so the demo path would have
stored nothing. `B007 loop control variable not used` caught it. `accept` now
takes an optional `text` for a caller that has it in hand and no store to fetch
from, and the comment says the event path never supplies it.

**An architecture rule I chose not to bend.** `TrigramSimilarity` memoised its
trigram vectors, which `test_module_state.py` refuses. The `DERIVED_INDEXES`
exemption K02 added requires state recomputable from a repository, and this was
a memo of a pure function keyed by its own argument, so it did not qualify and
the honest options were a second exemption or no memo. Bending an architecture
rule for a micro-optimisation on a batch job is a bad trade, so the memo is
gone and the class holds no state.

## Contract and plan notes

- **OpenAPI snapshot regenerated.** `GET /v1/demo/autopsy` now returns the
  staff views rather than a per-request report. The response shape changed, and
  it is a `tags=["demo"]` route behind `DESK_QUEUE_READ` with no frontend
  consumer, so this is a deliberate change rather than a break.
- **No new event.** `complaint.created` already existed in
  `contracts.events` and in plan 21 section 11.3 as produced by channels and
  consumed by autopsy. AU01 is the consumer that entry promised.
- **No new module edge.** `"autopsy": set()` still holds: the service reaches
  the complaint store through a protocol the composition root fills, the same
  arrangement C02 used for the flow tools.
- Collections `autopsy.complaints` and `autopsy.clusters` registered.

## Docs updated

- This devlog, `backend/src/clarity/modules/autopsy/MODULE.md`,
  `CHANGELOG.md`, `ARCHITECTURE.md`, `plan.md` (#13 ticked).
- No `.env.example` change.

## Tests run

- `make check`: **1694 passed, 544 skipped** (1679 before AU01).
- `make contracts-check`: passes after regeneration.
- Acceptance 1: an unreviewed cluster's staff view carries `hypothesis: true`,
  the exact label, `reviewed_by: null` and `acted_on: false`; a suggested rule
  on one is marked a guess; and a confirmed cluster still says it is not a
  published rule.
- The review workflow: a verdict is a record and not a label edit, a second
  verdict is refused, superseding keeps the one it replaced and needs a reason,
  an anonymous verdict is refused, and a re-run keeps reviewed clusters.
- The event feed: the consumer reads text from the store and not the event
  (and the event still has no text field), a redelivery does not inflate a
  cluster, only masked text is stored, a complaint quoting a credential is
  never stored, and a complaint with no text is not an error.
- Non-vacuity, two probes: removing the hypothesis label from the staff view
  fails acceptance 1 and the confirmed-label test; making the stored complaint
  key unique per call fails the redelivery test.

## Known gaps

- **No embedding model** (above), so clustering is character overlap over a
  canonical form. The largest gap and the same one K02 and K03 carry.
- **Nothing produces `complaint.created`.** The consumer is wired and idle
  until the channels work lands. `GET /v1/demo/autopsy` seeds the demo
  complaints on first call so the path is demonstrable meanwhile, and that
  seeding is the one caller that passes text directly.
- **No serverless packaging.** `rerun` is the batch entry point and the code is
  ready to be invoked by one, but there is no function package, no schedule and
  no deployment artefact. That is R7 deployment work with nothing to test here,
  and I would rather say it is missing than ship a wrapper and call it done.
- **No staff UI.** `GET /v1/demo/autopsy` returns the labelled views; the
  console does not render them, and the review verdict has no route of its own,
  so `review` is reachable from code and tests only.
- `CANONICAL_TO_RULE` maps a canonical phrase to a rule id in code. Like the
  Singlish lexicon C04 moved, this is content and belongs under the policy
  lifecycle rather than in a module constant.
- The clustering similarity threshold (0.45) is a module default that nothing
  has tuned on anything.

## Next step

Wave 4's remaining items, and the three gaps that now span several work
packages: an embedding model (K02, K03, AU01), a recorded cassette so any model
path is exercised at all (C03, C04, K03), and publishing content artefacts
through `PolicyGovernance` (C02, K01, AU01).

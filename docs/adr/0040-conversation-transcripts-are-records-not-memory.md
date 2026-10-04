# 0040 - Conversation transcripts are records, not memory

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Pasidu-Mihiranga |
| Plan references | enterprise-plan/22 §9; enterprise-plan/11 §19; deck S8 |

## Context

Plan 22 §9 says, without qualification: "No long-term memory of conversation content." `clarity.modules.conversation.state` quotes that line as the reason it keeps flow, state, slots, language, a proposal pointer and a turn counter, and nothing else. The audit trail does not fill the gap either: `TurnRecord.to_detail` carries the masked *kinds* a message contained, never its words.

The result is that the words of a conversation exist nowhere on the server. Three things depend on them and none of them work:

1. **A handoff has no context.** A flow decides `handoff: true` and names a queue, and the agent who picks the case up has no way to see what the customer already explained. The customer repeats themselves, which is the specific failure the product exists to remove.
2. **A customer cannot look back.** The chat keeps up to twenty threads in `localStorage`, storing assistant turns as a card `kind` with no text. Clearing the browser loses it, a second device never had it, and after A1 the reply it would need to show is now real text rather than a card name.
3. **A dispute has no document.** "Clarity told me it would be refunded" cannot be checked by anyone, in either direction.

The force against keeping it is real and is the reason §9 is written the way it is: a telecom assistant that accumulates what customers say, under PDPA No. 9 of 2022, with the deck's own "Foresight on aggregates only" posture next to it, is a liability that grows quietly.

## Decision

Keep a transcript of each conversation as a **record**, and make it structurally incapable of being **memory**.

The distinction is the decision, not a framing of it. What §9 is protecting against is content that accumulates and then steers a later answer: memory that decides. A record that no part of the turn pipeline can read is not that, in the same way the audit trail is not that. So:

- `conversation.transcripts` holds one row per speaker per turn: masked text, turn number, role, language, channel, timestamp, expiry.
- The orchestrator writes it **after** the reply has been composed, verified and substituted if verification failed, so what is stored is what the customer was actually told.
- Text is `MaskedText.text`, never the raw message. Forbidden content (OTP, card, CVV, PIN) never reaches the module, because those turns are refused before composition.
- The collection is **append-only** and listed in `platform.persistence.schemas.APPEND_ONLY`, grant-backed in `full`.
- Retention is 90 days (**ASSUMPTION - REQUIRES HUTCH CONFIRMATION**), applied by expiry on read, so a sweeper that has not run cannot surface a line past its window.
- It is read only through `GET /v1/cases/{case_id}/transcript`, which carries `case:read` and the same subject binding as every other case route.
- **Nothing in the turn pipeline may read it.** `tests/architecture/test_transcript_is_not_memory.py` asserts that no file that decides a turn calls `for_case`, that `transcript.py` imports nothing from the deciding modules, and that the write happens after verification.

This amends plan 22 §9, which is updated in the same change to say what it actually means.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Leave it as it is | The three failures above are all real today, and the first one undermines the handoff path the product depends on. "No server-side record" is not privacy, it is an absence of a feature with a privacy argument attached. |
| Keep it only in the browser, as now | Already the status quo and already failing: it is per-device, it is lost on a cache clear, it stores card names rather than text, and a staff member can never see it. It also puts the only copy of a conversation somewhere Clarity cannot apply retention to. |
| Put it in the audit trail | The trail is hash-chained, effectively permanent, and read by auditors under a grant. Customer words do not belong in a structure designed never to be deleted, and `_FORBIDDEN_SEGMENTS` exists to keep exactly this out of event payloads. |
| Store unmasked, mask on read | One bug in a read path leaks it, and the masker already runs before anything is stored. Masking at write means the clear text never exists at rest. |
| Summarise each conversation instead of keeping it | A summary is a model's account of what someone said, presented as a record. Worse than keeping nothing for a dispute, and it would be memory by definition. |

## Consequences

Positive:
- A handoff carries what was said, so the agent starts where the customer left off.
- A customer sees their history on any device, within retention.
- A dispute about what Clarity said has a masked, append-only, timestamped answer.

Negative, and accepted:
- Clarity now stores customer words, where it previously stored none. This is the real cost of the decision and it is why retention, masking, append-only and subject binding are all part of it rather than follow-ups.
- The `full` profile needs the append-only grants extended to a second table.
- Retention is an assumption that HUTCH has to confirm; the number is wrong until they do.

What must now be true:
- `tests/architecture/test_transcript_is_not_memory.py` passes.
- `conversation/MODULE.md` describes the collection, its retention and the read route.
- Plan 22 §9 no longer says something the code contradicts.

## Compliance

- **CI.** The architecture test fails the build if any file that decides a turn reads a transcript, if `transcript.py` imports a deciding module, or if the write moves before verification.
- **Data ownership.** `tests/architecture/test_data_ownership.py` already requires every collection to have an owner named for it, so the table cannot be added to another module.
- **Review rule.** A change that reads `for_case` from anywhere other than an interface is a change to this ADR, not a refactor.

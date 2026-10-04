# 0041 - A session has an absolute deadline

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Pasidu-Mihiranga |
| Plan references | enterprise-plan/11 §19 (TH5, TH9); enterprise-plan/19 §4 |

## Context

`TokenIssuer` had two lifetimes: a short access token (ten minutes for a customer, eight hours for staff) and a refresh token at thirty days. The refresh window looked like the bound on a session, and it was not.

`refresh_expires_at` was computed as `now + REFRESH_TOKEN_TTL` inside `_issue`, and `refresh` issues. So every refresh started a fresh thirty-day window. A session refreshed once a month never expired. The practical consequences:

- A stolen refresh token is a permanent credential. The customer proved possession of their phone with a one-time code once, perhaps a year ago, and nothing ever asks again.
- A customer who signed out on a lost handset has no way to know a session is still alive somewhere, and neither does anyone else: nothing bounds it.
- "Thirty days" appeared in the code, in the settings and in review, and bounded only the *idle* case that nobody was worried about.

The sliding window is not the mistake. It is exactly right for expiring a session nobody is using. The mistake was having only that.

## Decision

A session carries the moment it began, and ends a fixed interval after it, whatever happens in between.

- `SessionRecord.started_at` records the authentication that started the session. `refresh` carries it forward unchanged into the session it issues.
- `refresh` refuses once `now >= started_at + ABSOLUTE_SESSION_TTL`. The person signs in again and proves who they are.
- `refresh_expires_at` is `min(now + REFRESH_TOKEN_TTL, started_at + ABSOLUTE_SESSION_TTL)`, so a refresh token handed out near the end of a session's life expires with the session rather than outliving it.
- `ABSOLUTE_SESSION_TTL` is thirty days (**ASSUMPTION - REQUIRES HUTCH CONFIRMATION**), matching the refresh window that was already there, so an actively used session now ends where an idle one always did.
- Records written before this field existed read back as having started when they were last issued, so the cap applies from that point rather than signing everybody out on deploy.

Alongside it, because the two are the same question asked by a person rather than by a clock: `GET /v1/auth/sessions` lists a subject's own live sessions and `DELETE /v1/auth/sessions` ends them.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Leave it | The bound everyone believed existed did not. That is worse than no bound, because nobody was looking for one. |
| Shorten `REFRESH_TOKEN_TTL` | Treats the symptom. A one-day sliding window still never ends for a session used daily, which is every session that matters. |
| Re-prove assurance on refresh instead of ending the session | Means an OTP prompt mid-journey on a schedule the customer cannot predict. The honest moment to ask somebody to sign in again is when their session has ended, not in the middle of a dispute. |
| Downgrade the assurance over time rather than ending the session | A customer session has one usable level. Downgrading it to `NONE` is ending the session while pretending otherwise, and it would fail at the next action rather than at the door. |
| Bound it in the database with a scheduled sweep | A sweeper that has not run is not a reason to honour an expired session. Expiry is enforced on use, as it is for conversation state and OTP challenges; sweeping is housekeeping for the table. |

## Consequences

Positive:
- A session ends. A stolen refresh token is bounded by the deadline rather than by whether anybody notices.
- A person can see every device holding their session, and end them.
- `keep_current` defaults to true on the bulk sign-out, so somebody who has just found a session they do not recognise does not also sign themselves out of the device they are holding while dealing with it.

Negative, and accepted:
- Every customer signs in again at least once a month, including ones who never stopped using the app. That is the point, and it is the cost.
- `sessions_for` scans the collection. Honest at these sizes and wrong at HUTCH's: the `full` profile wants an index on the subject, which is a migration rather than a change to this decision.
- Thirty days is an assumption. It is a number HUTCH has to confirm, and it is the kind of number that gets confirmed only after somebody asks what it is for.

## Compliance

- `tests/unit/test_iam.py` asserts that a session refreshed regularly still ends at the deadline, that the deadline is counted from the first sign-in and not the latest refresh, and that a refresh token never outlives its session.
- The same file asserts the inventory shows only the subject's own sessions, that a revoked session leaves the list, and that signing out everywhere spares the current device and touches nobody else's sessions.
- `tests/acceptance/test_staff_sso_routes.py` asserts the list carries nothing that could resume a session.

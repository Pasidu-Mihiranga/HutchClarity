# 2026-10-04 - SMS04 - Preserve OTP after a network change

## What changed

- Live SMS requests no longer call the synthetic inbox route.
- A network interruption during verification explains that the code was not
  submitted and leaves the same challenge ready for another Sign in attempt.
- Added browser coverage for both behaviors.

## Why

The browser changed networks while submitting an OTP. No verification request
reached the API, but the generic `Failed to fetch` message made this look like
an invalid code. Live delivery also produced an unrelated synthetic-inbox 404.

## Validation

- Live API request plus verification against the stored challenge: HTTP 200
  and a signed session token was issued.
- Focused browser test: 1 passed.
- Customer-web production build: passed. Next.js emitted its existing optional
  SWC lockfile patch warning after producing the build.
- The complete browser suite exposed a pre-existing race in the voice privacy
  disclosure: a fast transcript hid the disclosure before it could be read.
  The notice now remains visible while the customer reviews the transcript.
- CI traces also showed authentication responses incorrectly carrying the
  anonymous assistant limiter's headers under concurrent CORS traffic. The
  limiter now runs at the ASGI message boundary with request-local response
  headers, and an exhausted assistant budget is verified not to mark an
  unrelated endpoint as rate limited.

## Next step

Deploy, request one fresh code, and retry immediately on a stable connection.

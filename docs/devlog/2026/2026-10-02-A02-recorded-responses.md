# 2026-10-02 - A02 - Recorded responses, and a suite that cannot call a model

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | A02 (issue #3), Wave 2; plan 19 section 4.3 |
| Units touched | `clarity.ai` (`cassettes.py`), `tests/support/no_network.py`, `tests/conftest.py`, `cassettes/` |

## What changed

- `ai/cassettes.py`: a cassette is a plain JSON file holding the prompt and the answer. `RecordedProvider` wraps any provider and replays instead of calling it; in replay mode the wrapped provider is never touched.
- `tests/support/no_network.py`: the socket layer is closed for the whole suite. Anything leaving the machine raises `LiveCallAttempted` naming the host.
- `tests/conftest.py`: the guard is **autouse and unconditional**.
- `cassettes/README.md`: what a cassette is, how to read one, how to record one.

## Why

Issue #3: any future model test would have called a live endpoint.

## Decisions made

- **A missing cassette is an error, not a live call.** Falling through to the network is the failure A02 exists to prevent: a suite that quietly reaches a provider is one rate limit away from a red build nobody caused.
- **The network is closed, not merely discouraged.** A cassette that is only *preferred* is not a guarantee, and a guard a test can forget to apply is not a guard. So it is autouse and enforced at the socket layer, which holds for any HTTP client rather than only the one we happen to use.
- **Resolution is guarded as well as connection**, and that is the half that makes the failure readable. By connect time the hostname is already an IP, so the first version reported `('2a06:98c1::6812:26ec', 443)`, which tells nobody which provider was called. Catching `getaddrinfo` reports `api.groq.com:443`.
- **Loopback stays open.** The suite legitimately talks to itself: `TestClient` drives the app, and the `full` lane talks to PostgreSQL, Kafka, OPA and OpenBao on localhost. Those are components under test, not endpoints that cost money.
- **The key covers the whole prompt, the provider and the model.** A reworded prompt misses its old cassette rather than replaying an answer to a different question, which would be the worst kind of passing test. A different model gets its own recording, because it can answer differently.
- **The prompt is stored, not just the answer**, so a cassette reads in a diff. A cassette whose answer no longer fits its prompt is the interesting case and is invisible without it.

## Tests

- `tests/unit/test_cassettes.py` (new, 10 tests): acceptance 1 both directly and through the real routing path, a missing cassette refusing rather than calling, recording writing a reviewable file, key sensitivity to prompt and model, the outbound block at both the HTTP and raw socket layers, loopback still working, and a check that no committed cassette contains a raw number (I13).
- `make check`: **1251 passed, 512 skipped**. The guard is in force for all of them.

Verified non-vacuous: removing the autouse guard from `conftest.py` lets a real connection to `api.groq.com` succeed and fails both refusal tests.

## Open issues / note

- **No cassettes are committed yet**, because no code path calls a provider in a test today. The machinery is in place and proven; the first real recordings arrive with A05's evaluation harness and whichever flow first uses the `reason` role. The directory holds only its README.
- `CLARITY_RECORD_CASSETTES` is read by whoever constructs the library, not by `Settings`. It should be a declared setting like every other variable (B07) once the container wires the router.

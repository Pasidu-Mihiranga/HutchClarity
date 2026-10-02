# 2026-10-02 - A01 - Model roles, provider chains and quota-aware buckets

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code (Opus 5) |
| Work package | A01 (issue #2), Wave 2; I12, ADR-0009, plan 19 section 4 |
| Units touched | `clarity.ai` only (`roles.py`, `buckets.py`, `local.py`, `routing.py`, `providers.py`, `__init__.py`), `config/ai/models.yaml`, tests |

## What changed

- `ai/roles.py`: the eight roles and a loader for `config/ai/models.yaml`, which was present but read by nothing. A role resolves to an ordered chain of (provider, model).
- `ai/buckets.py`: token buckets per provider with priority. **Customer live keeps a reserved share of every window that nothing else may spend.**
- `ai/local.py`: the local providers that end each chain.
- `ai/routing.py`: `RoleRouter.invoke(role, prompt, priority)` walks the chain, skipping a step that is unconfigured, over quota, rate limited or broken, and records why.
- `ai/providers.py`: `ProviderRateLimited` split out of `ProviderError`, because a 429 means "try the next provider" while a malformed response means this provider is misconfigured and the next probably is too. On a free tier the 429 is the ordinary case.
- `config/ai/models.yaml`: a local last step added to the four chains that lacked one.

## Why

Issue #2. The gateway routed by tier for explanations only, and the config file that was supposed to decide which model does what was read by nothing.

## Decisions made

- **All four missing chains got a local terminator**, which you asked for after I flagged that `extract`, `reason`, `judge` and `stt` had no answer at all with no provider configured, while acceptance test 1 requires *any* role to answer from a template or rule at zero tokens.

  Two of them do real local work: `extract` falls back to keyword rules, which is the path C04 wants tried first anyway, and `reason` falls back to the same approved templates as `fast-text`.

  **The other two answer by saying they cannot, and that is the honest version of what you asked for.** There is no local way to judge an output's quality or to transcribe speech. A fabricated score would be averaged by the evaluation harness and trusted by a release gate; a guessed transcript is invented customer input, which is exactly what I2 exists to prevent. So `judge` returns "unscored" and `stt` returns "transcription unavailable", deterministically, and `RoleAnswer.is_refusal` marks them so a caller routes to a person rather than acting on words nobody said. Every role now terminates locally and spends nothing, which is what the acceptance test asked; none of them pretends.

  `test_the_roles_that_refuse_locally_are_the_expected_two` pins that set, so a third role cannot quietly start returning a non-answer in place of a real capability.

- **A customer reserve rather than a shared pool.** A free tier is one ceiling shared by everything, so without an allocation the first batch job of the day can spend it all and the customer asking "why was I charged" is the request that fails. That is the one request that must not. Batch stops at the reserve; customer-live may spend the whole window.

- **Buckets claim an estimate before the call and correct it after**, because a ceiling that is only checked after spending is not a ceiling.

- **An unconfigured provider is skipped, not an error.** A deployment with no Groq key is a supported deployment (ADR-0006).

## Docs updated

- [x] `config/ai/models.yaml`: the four local terminators, each with the reason in a comment
- [ ] `ARCHITECTURE.md` / `docs/modules.md`: deferred with the container wiring below
- [ ] CHANGELOG.md: no `/v1` contract change; nothing in the HTTP surface moved

## Tests

- `tests/unit/test_ai_roles.py` (new, 19 tests): acceptance 1 parametrised over all eight roles, acceptance 2 for a 429 falling through, plus an unconfigured step, a broken provider, the customer reserve, window reset, and config validation.
- `tests/architecture/test_no_model_ids.py` (new, 4 tests): acceptance 3. It takes the model IDs **from the real config** and searches the source for them, so adding a provider cannot slip past a hard-coded list. It also asserts the config still names at least five models, so the test cannot pass by finding nothing to look for.
- `make check`: **1241 passed, 512 skipped**.

Both acceptance tests verified non-vacuous:
- removing `stt`'s local terminator from the config fails four tests across both files;
- making the router not catch `ProviderRateLimited` fails the fall-through test.

I12 already held before this change: no model ID was found anywhere in the source.

## The wiring (added once the tree was quiet)

`app/container.py` now builds the catalogue, the buckets, the router and the
guard. Verified end to end: with no provider configured the running app resolves
all eight roles at zero tokens, and `judge` and `stt` return refusals.

- **Every local provider is always bound**, which is what makes "no model configured" a supported state rather than an outage. A remote name is bound only when this deployment has that provider, and an unbound name is skipped by the router rather than being an error.
- **Remote providers are wrapped in a cassette.** In replay mode a test cannot reach the network even when a key is present (A02). The two wrappers are chained deliberately: the router walks the chain, and whatever it lands on is already recorded.
- **`CLARITY_RECORD_CASSETTES` and `CLARITY_MODELS_FILE` are now declared settings** (B07), which the architecture test caught: it failed until both appeared in `.env.example`.
- `RecordedProvider.name` became a plain attribute rather than a property, because the `ModelProvider` protocol wants it settable and mypy was right to refuse the property.

## Open issues / next step
- **No quotas are declared yet.** `TokenBuckets` is built empty, so nothing is metered until a deployment adds a `ProviderQuota`. That is the honest state: the free-tier numbers should come from `config/ai/models.yaml` alongside the chains so Risk sees the whole picture in one file, and inventing numbers here would have been worse than leaving it visible.
- Quotas are otherwise declared in code by whoever builds `TokenBuckets`; the free-tier numbers should come from `config/ai/models.yaml` alongside the chains so Risk can see the whole picture in one file.
- `AIGateway.explain` and `RoleRouter.invoke` are two entry points to the same layer. `explain` should become a caller of the `fast-text` role rather than its own path, which is best done with the container wiring above.

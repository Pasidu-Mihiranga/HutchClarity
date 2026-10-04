# 2026-10-04 - Audit assurance Phase 2 - Signed checkpoints and a public witness

| Field | Value |
|---|---|
| Author(s) | Thanoj Buddhima; agent: Claude Code |
| Work package | `docs/audit-assurance-plan.md` Phase 2, ADR-0035 |
| PR / commit | branch `claude/affectionate-hamilton-ww2hgz` |
| Units touched | platform.audit (new `checkpoints.py`), app (container, settings), interfaces.http, config/policy |

## What changed

- `Checkpointer`: signs `(seq, chain_head, recorded_at)` on a policy schedule
  with a key separate from the receipt key, and verifies the trail against the
  chain and every checkpoint.
- `config/policy/audit.yaml`: 50 records or 15 minutes between checkpoints.
- `GET /.well-known/clarity-audit-checkpoint.json`: the latest checkpoint and
  its public key, for anyone to keep.
- Startup verification uses the checkpoints; a demo reset carries the
  checkpointer so the key does not change under earlier checkpoints.

## Why

A chain cannot detect a consistent rewrite or a cut with a rewound head. Both
were staged in tests and both fooled `verify()`; the checkpoints catch both.

## Decisions made

- **Loss reports use the highest checkpoint, after all signatures pass.** The
  first version stopped at the first checkpoint past the trail's end and
  reported records 4 to 5 lost when a later checkpoint proved records up to 13
  existed. The test caught it; a loss report that understates the loss is the
  failure this phase exists to prevent. Signatures are checked first so a
  forged checkpoint cannot inflate the report either.
- **Platform cannot import the receipt signer (I4)**, so the checkpointer takes
  a two-method protocol and verifies Ed25519 from public material itself.
- **Key persistence follows the trail.** `full` without OpenBao keeps the key
  in `KEYS_DIR` so checkpoints verify after a restart; `demo` keeps it in
  memory because the trail is in memory too.
- **Deferred with reasons (ADR-0035):** cross-anchoring into the receipt chain
  (a receipt contract change), incremental verification (performance, not
  correctness), keyed payload hashes (key custody decision).

## Docs updated

- [x] ADR-0035 and the index
- [x] CHANGELOG.md; OpenAPI snapshot regenerated on purpose (one route added),
      `contracts/openapi.json` and SDK types regenerated
- [x] `.env.example`: `CLARITY_AUDIT_SIGNER_KEY_NAME`
- [x] Plan revision 5
- [x] Route contract: the new route classified PUBLIC

## Tests

- `make check` on the committed state: lint and format clean, `mypy --strict`
  clean (218 files), contracts 3 kept 0 broken; **`1 failed, 2057 passed, 544
  skipped`**. The failure is the container-proxy test, as in every run here.
  The OpenAPI snapshot was regenerated on purpose and its diff is the one new
  route. `make contracts-check` passes.
- `tests/unit/test_audit_checkpoints.py`: 10 tests, each an attack: consistent
  rewrite, cut with a rewound head (loss range asserted), checkpoints deleted
  too and caught by a witness, forged checkpoint, key rotation, separate keys,
  startup refusal, public endpoint round trip.

## Open issues / next step

- Phase 3: audit grants under separation of duties, `GET /v1/audit`, audited
  reads, recertification and break-glass.
- The three deferred Phase 2 items and database-level append-only (W1).

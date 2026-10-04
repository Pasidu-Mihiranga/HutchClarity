# 0035 - Signed audit checkpoints with a separate key, and a public witness

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Thanoj Buddhima |
| Plan references | `docs/audit-assurance-plan.md` (Phase 2, section 5.4), ADR-0033, ADR-0034 |

## Context

After ADR-0033 and ADR-0034 the trail detects any edit to any field and lives
in one persisted chain. It still cannot detect an insider with full write
access who **rewrites every record and the head consistently**, or who cuts the
newest records off and rewinds the head to match: the chain they leave behind
verifies. Both were staged in tests and both fooled `verify()`.

The maintainer's constraint is enterprise-grade assurance with no new
infrastructure, so write-once storage is out.

## Decision

1. **Signed checkpoints.** A checkpoint signs
   `(purpose, seq, chain_head, recorded_at)` with Ed25519. Verification checks
   the chain, then every checkpoint's statement and signature, then that the
   trail still has that head at that `seq`. A trail shorter than a genuine
   checkpoint is reported with the exact range lost, up to the **highest**
   checkpoint.
2. **A separate key.** `CLARITY_AUDIT_SIGNER_KEY_NAME` in OpenBao, or a local
   Ed25519 key, never the receipt key, so a compromise of one cannot forge the
   other. In `full` without OpenBao the key is kept in `KEYS_DIR` so
   checkpoints verify after a restart. Rotation keeps old public keys, so old
   checkpoints still verify.
3. **The schedule is policy.** `audit.checkpoint.every_records` (50) and
   `audit.checkpoint.max_age` (PT15M) live in `config/policy/audit.yaml`,
   resolved when they apply (I10). The first record is checkpointed at once.
   Each checkpoint is itself recorded as `checkpoint.issued`.
4. **A public witness.** `GET /.well-known/clarity-audit-checkpoint.json`
   serves the latest checkpoint with its public key. Anyone who saves one holds
   a copy the database cannot alter; `verify(witness=...)` uses it to catch an
   insider who also deleted the stored checkpoints.
5. **Startup verifies against checkpoints**, not only the chain, so a process
   refuses to serve a trail cut below a signed checkpoint.

The checkpointer is `platform` code and cannot import the receipt signer
(I4), so it declares the three signer methods it needs as a protocol and
verifies Ed25519 from public material only, as an outside verifier would.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Write-once storage | New infrastructure, against the constraint. A key outside the database gives the same property for detection. |
| Sign every record | A key operation per write. Checkpoints bound the undetectable window to the policy interval at a fraction of the cost. |
| Reuse the receipt key | One compromise would forge both receipts and checkpoints. |
| RFC 3161 trusted timestamps now | An external service. Recorded as an optional production upgrade. |

## Deferred, deliberately

- **Cross-anchoring the head into the receipt chain.** It changes the signed
  receipt payload, which is a receipt contract change with its own review. The
  public witness already gives an external copy.
- **Incremental verification.** Verification still walks the whole chain;
  verifying from the last checkpoint forward is an optimisation that matters
  at production volume, not for correctness.
- **Keyed payload hashes.** Needs a decision on where the HMAC key lives and
  how it rotates. Today's payloads carry pseudonyms, not phone numbers, and a
  test asserts no number reaches the trail.

## Consequences

- The window an insider can rewrite without detection is bounded by the
  checkpoint interval, and only for someone who also holds the signing key.
- A lost checkpoint key in `lite` or `full`-without-OpenBao makes old
  checkpoints unverifiable; key custody is part of the RACI in the plan.
- `/.well-known/clarity-audit-checkpoint.json` is a new public route and an
  OpenAPI change, regenerated with the SDK types.

## Compliance

`tests/unit/test_audit_checkpoints.py` stages each attack: a consistent
rewrite, a cut with a rewound head (with the loss range asserted), deleted
checkpoints caught by a witness, a forged checkpoint, key rotation, separate
keys, startup refusal and the public endpoint.

## Amendment, 2026-10-04: incremental verification, and what it does not cover

`Checkpointer.verify(incremental=True)` and `AuditLedger.verify(since=, since_hash=)`
recompute record hashes only from the newest checkpoint that verifies upward, so
the work is bounded by what was written since that checkpoint rather than by the
length of the trail. That is what lets the liveness heartbeat run on a minute's
cadence on a trail of any size.

**The obvious claim for it is false, and was written down before it was tested.**
The first version of this ADR argued that because a chain hash commits to its
predecessor's, checking one hash at the anchor covers every record below it. It
does not. Edit record 3 and recompute only record 3's own `chain_hash`: records 4
upward still carry the `prev_hash` they always had, so the hash at the anchor is
unchanged and the dangling link between 3 and 4 sits below everything the
incremental check recomputes. A test caught this.

What an incremental check therefore covers:

- every record from the anchor upward, exactly as a full check does;
- the anchor row's own contents, which are recomputed rather than hash-compared,
  because nothing above the anchor depends on them;
- the shape of the chain below the anchor, meaning the sequence of hashes those
  rows *claim* to have is the sequence the checkpoint signed;
- truncation, including of the anchor itself.

What it does not cover: the contents of a row below the anchor. So the full
recompute stays the default and the tamper check, runs at startup and on the
policy interval, and the incremental check is the freshness check between two of
them. A forged checkpoint is never used as the anchor: every checkpoint's
signature is verified first, and a failure there disables the optimisation.

`tests/unit/test_audit_checkpoints.py` pins all of this, including a test that
asserts the limitation rather than hiding it, so nobody reads the parameter as
a free upgrade.

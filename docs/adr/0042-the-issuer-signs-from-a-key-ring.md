# 0042 - The issuer signs from a key ring

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-04 |
| Deciders | Pasidu-Mihiranga |
| Plan references | enterprise-plan/11 §19 (TH9); enterprise-plan/19 §4; ADR-0013 |

## Context

`TokenIssuer` held one Ed25519 key, loaded from one PEM on a shared volume, and named it `clarity-iam-dev` in every token header it ever signed.

Nothing about that is wrong on its own. What it meant is that the key could not be changed. Replacing the file invalidates every token in circulation the moment the first process reloads: every signed-in customer and every staff member is signed out, mid-journey, with no warning. A key rotation that does that is not a rotation, it is an outage, so in practice the key is never rotated and TH9's mitigation stays on paper.

Two smaller things followed from the same shape. A fixed `kid` means a token cannot say which key signed it, so there is nothing to key a transition on. And `/.well-known/clarity-keys.json` published exactly one key, so any validator that is not this process would break at the moment of a change even if the issuer handled it.

## Decision

The issuer signs from a ring: one active key, plus any key retired within an overlap window.

- **Key ids are derived from the key**, as `iam-<first 16 hex of SHA-256 of the raw public key>`. Content-addressed rather than configured, so two processes loading the same key agree on its name without being told, and a new key cannot reuse the name of the one it replaced.
- **`rotate()` generates a new active key** and retires the current one with a timestamp. The retired key keeps verifying for `KEY_OVERLAP_WINDOW` (twelve hours, **ASSUMPTION - REQUIRES HUTCH CONFIRMATION**), which has to cover the longest-lived thing it signed: a staff session at `STAFF_TOKEN_TTL`, with room for a rotation that does not complete instantly across replicas.
- **`verify` selects the key by the token's `kid`.** A token naming a key this issuer has never held, or one whose window has closed, is refused before any signature check. That is what makes a retired key actually retire rather than merely stop being advertised.
- **`public_keys()` publishes the whole ring** and the well-known endpoint serves it.
- **The ring lives on the shared key volume.** The active key stays at `KEYS_DIR/iam-issuer.pem`; a retired key is written as `iam-issuer-retired-<kid>-<epoch>.pem`, which describes itself and needs no sidecar that could go missing separately.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Leave one key | The rotation is then theoretical. A control nobody can exercise without an outage is a control nobody exercises. |
| Rotate by restarting every process at once | Still invalidates every token in circulation, and requires a coordinated restart to do it. The overlap exists precisely so the change does not have to be instantaneous. |
| Keep the ring in a repository | A private key in an application table is a different risk posture from a key on a mounted volume: it is in backups, in replicas, and in reach of anything holding the module's database role. The volume is already how the current key is shared. |
| Keep the ring in process memory only | Tried, and `tests/architecture/test_module_state.py` refused it, correctly. A rotation on one replica would be invisible to the others, which keep signing with the key it retired and cannot verify its new tokens. That reads as intermittent sign-outs rather than a configuration fault, which is the worst way for it to fail. |
| Sign through OpenBao Transit, as receipts do | Right for receipts: low volume, high value, and the signature is the product. A token is minted on every sign-in and every refresh, so remote signing puts a network call and a new failure mode on the authentication path. The seam this ADR adds is what such a move would need; the move itself is a separate decision, deliberately not taken here. |
| Configured key ids | A name somebody types can be wrong, can be reused after a rotation, and tells you nothing about the key it names. |

## Consequences

Positive:
- The key can be rotated without signing anybody out, which is what makes TH9's mitigation real.
- A token says which key signed it, so a transition is observable.
- An external validator reading the well-known endpoint survives a rotation.

Negative, and accepted:
- A retired key is still on disk and still verifying for the overlap window. That is the trade: a key compromised badly enough to need immediate revocation needs the window set to zero and the sign-outs accepted, which is a deliberate act rather than the default.
- Twelve hours is an assumption, and it is coupled to `STAFF_TOKEN_TTL`. Changing one without the other leaves tokens that cannot be verified.
- Key files accumulate until their window closes. They are dropped from the ring on load and on rotation rather than by a sweeper, so a stale file is inert, but it is still a file.

## Compliance

- `tests/unit/test_iam.py` asserts that a key is named after itself, that rotation does not invalidate an existing token, that new tokens use the new key, that a retired key stops verifying when its window closes, that the published ring carries every key a validator needs and drops one past its window, and that a token naming an unknown key is refused.
- The same file asserts a rotation survives a restart and that a second process honours a rotation it did not perform.
- `tests/architecture/test_module_state.py` is what caught the in-memory version, and still guards the shape.

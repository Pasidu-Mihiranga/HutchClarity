# 2026-10-04 - DEP01/CD01 - single-VPS deployment

| Field | Value |
|---|---|
| Author(s) | agent: Codex |
| Work package | DEP01 and CD01 (plan 21 §7 R7) |
| PR / commit | pending |
| Units touched | app composition, frontend packaging, deploy, CI/CD |

## What changed

- Added one private Compose topology, a generic non-root frontend image and an Nginx IP-HTTPS boundary.
- Added idempotent bootstrap, backup, deploy, health, certificate and rollback scripts.
- Added CI-approved SHA image publication and VPS deployment without replacing existing CI.
- Wired the configured receipt verification base and persistent synthetic signing key.

## Why

DEP01 #57 and CD01 #58 require a verified hackathon deployment before WA01 #59
can start. The existing `full.yml` remains development-only.

## Decisions made

- Docker Compose is used for this 2-vCPU, 4-GB single VPS; Kubernetes is not introduced.
- The development Ed25519 signer is persisted only because every receipt and customer is synthetic.
- Let's Encrypt short-lived IP certificates renew every six hours through Certbot 5.8 webroot mode.

## Docs updated

- [x] Deployment and frontend READMEs
- [x] Backlog and changelog
- [x] ARCHITECTURE.md after live verification
- [x] Demo script after live journeys

## Tests

- Focused settings tests: 9 passed.
- `make check`: 1,998 passed, 544 skipped; Ruff, strict mypy and three import contracts clean.
- Three Next.js standalone builds passed; generic customer image built, started and served as uid 10001.
- VPS Compose configuration validated after bootstrap.
- First live start failed because PostgreSQL 18 rejects the pre-18 child volume
  mount. First-deployment rollback restored all ten previously running
  BikeRentHub containers healthy; the mount was corrected to the versioned
  cluster parent before retry.
- Second start made all 12 services healthy. Trusted IP HTTPS, customer OTP,
  evidence, deterministic decision, safe action, persisted receipt verification,
  staff queue, Autopsy and Foresight passed live. All internal ports were closed
  from the public Internet.
- A compressed PostgreSQL backup was created and validated. Restarting the API
  preserved both the receipt signing public key and the issued receipt. The
  Certbot staging renewal and deploy hook succeeded.

## Open issues / next step

Land on `main`, exercise CD and its no-rebuild rollback, then begin WA01.

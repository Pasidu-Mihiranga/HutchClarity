# Single-VPS demo deployment

This directory deploys the `full` profile to one VPS with Docker Compose. It is
for synthetic hackathon data only. It is not the HUTCH production topology and
does not use `deploy/compose/full.yml`, whose public ports and development
credentials are intentionally unsuitable for an Internet host.

## Public and private boundaries

| Address | Purpose |
|---|---|
| `https://116.203.101.73/` | Customer app and same-origin `/v1` API |
| `https://116.203.101.73:8443/` | Clarity Desk and same-origin `/v1` API |
| `https://116.203.101.73:9443/` | Trust Receipt verifier and same-origin `/v1` API |

PostgreSQL, Kafka, Keycloak, OPA, the API, MCP, channel gateway, `hutch-sim`,
the opt-in Baileys transport and all Next.js origin ports stay on the private
Compose network. Only SSH,
HTTP for ACME and redirects, and the three HTTPS listeners are allowed through
the host firewall.

## Bootstrap

Run `deploy/scripts/vps-bootstrap.sh` once as root after copying `deploy/` and
`config/` to `/opt/hutch-clarity`. Pass the dedicated CI public key through
`DEPLOY_PUBLIC_KEY`; never put a private key in the repository. The script:

- creates `clarity-deploy` and `/opt/hutch-clarity` with restrictive modes;
- creates `.env.production` once with random PostgreSQL, Keycloak, webhook and
  subscriber-pseudonym keys;
- creates a temporary IP-bound certificate only for bootstrap;
- installs Certbot 5.4 or newer and enables the six-hour renewal timer;
- opens 8443 and 9443 without changing the SSH rule.

Application secrets remain in `/opt/hutch-clarity/.env.production` and CD never
replaces that file. `SIGNING_KEY_PATH` points at a persistent volume. This is a
development Ed25519 signer for synthetic receipts, not a KMS or HSM.
Vertex credentials and the staff directory are files under
`/opt/hutch-clarity/private/` (mode 0600), mounted read-only. CD does not
upload them. `GOOGLE_APPLICATION_CREDENTIALS` inside the container is
`/run/clarity-private/google-service-account.json`.

Customer OTP delivery can use the hosted httpSMS API. Set `HTTPSMS_API_KEY` to
the primary user API key and `HTTPSMS_SENDER` to the E.164 number of the
registered Android gateway phone. A `pk_` phone-scoped key cannot call
`/v1/messages/send`. Both settings are required together and remain only in
`.env.production`.

WhatsApp is disabled by default. To enable the Baileys transport, set
`COMPOSE_PROFILES=whatsapp` and `WHATSAPP_ENABLED=true` only after operator
pairing. Its auth volume contains long-lived Signal keys and must be protected
like an SSH private key. Pairing has no web route:

```bash
docker compose --env-file /opt/hutch-clarity/.env.production \
  -f /opt/hutch-clarity/deploy/compose/vps.yml --profile whatsapp run --rm \
  -e WHATSAPP_PAIRING_PHONE=<country-code-digits> clarity-whatsapp npm run pair
```

If WhatsApp refuses phone-number linking, use QR pairing from the same private
operator terminal by replacing the phone environment option with
`-e WHATSAPP_PAIRING_MODE=qr`. The QR and auth state must not be copied into
logs, tickets or the repository.

Baileys is an unofficial WhatsApp Web client and is not affiliated with Meta
or HUTCH. The transport is limited to direct customer messages and must be
operated in accordance with WhatsApp terms. The service ignores own messages,
groups, status, broadcasts, newsletters and unsupported system messages.

## HTTPS

After the stack answers with the temporary certificate, run
`deploy/scripts/https-renew.sh`. It requests the Let's Encrypt `shortlived`
profile for IP `116.203.101.73` through HTTP-01 webroot validation and reloads
Nginx. IP certificates last about six days, so
`clarity-cert-renew.timer` runs every six hours. Verify with:

```bash
systemctl status clarity-cert-renew.timer
systemctl list-timers clarity-cert-renew.timer
openssl s_client -connect 116.203.101.73:443 -servername 116.203.101.73 </dev/null
```

## Deploy, backup and rollback

```bash
/opt/hutch-clarity/deploy/scripts/deploy.sh <git-sha>
/opt/hutch-clarity/deploy/scripts/healthcheck.sh
/opt/hutch-clarity/deploy/scripts/backup.sh
/opt/hutch-clarity/deploy/scripts/rollback.sh
```

Deployments use immutable commit-SHA image tags. Before an upgrade, `deploy.sh`
creates a compressed PostgreSQL dump and keeps the newest seven. It records
`current-release` and `previous-release`, and a failed health check invokes the
rollback script without touching volumes. On the first failed deployment, the
script stops Clarity and starts the exact previous-project container list when
`previous-project-containers.txt` was supplied during the server audit.

Restore is deliberate: stop Clarity writers, decompress the selected dump into
`psql` as the configured PostgreSQL administrator, verify schema ownership,
then start and run `healthcheck.sh`. Never restore automatically during an
application rollback.

## Reseed the synthetic world

The `full` profile seeds the synthetic HUTCH world into PostgreSQL once, then
reloads it on every start. A release that changes the world itself (for
example the 078 subscriber numbers) needs a deliberate reseed. `seed.py`
replaces only the synthetic world tables (customers, accounts, events,
consents, complaints); cases, receipts and audit are untouched. Back up first:

```bash
ssh clarity-deploy@116.203.101.73 /opt/hutch-clarity/deploy/scripts/backup.sh
ssh clarity-deploy@116.203.101.73 \
  'docker compose --env-file /opt/hutch-clarity/.env.production \
     -f /opt/hutch-clarity/deploy/compose/vps.yml exec -T clarity-api python -' \
  < backend/scripts/seed.py
```

Restart `clarity-api`, `clarity-mcp`, `clarity-channel-gateway` and
`hutch-sim` afterwards so they load the new world, then run `healthcheck.sh`.

## CI/CD

The existing `.github/workflows/ci.yml` remains the merge gate. The separate
`deploy-vps.yml` workflow runs only after successful CI on `main`, or by manual
dispatch for a CI-approved main SHA. The `demo-vps` environment contains:

- `HETZNER_HOST`
- `HETZNER_USER`
- `HETZNER_SSH_PRIVATE_KEY`
- `HETZNER_KNOWN_HOSTS`

SSH host verification is pinned. The workflow builds backend, WhatsApp and
three frontend images in GHCR, tags all of them with the same immutable SHA, uploads
only versioned manifests/scripts, backs up, deploys, and passes only after
health checks. Manual `rollback` reuses the recorded previous images and does
not rebuild. Repository settings should require every existing `ci` check on
`main` before merge.

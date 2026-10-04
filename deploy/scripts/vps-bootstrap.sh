#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "run as root" >&2
  exit 77
fi

install -d -m 0750 /opt/hutch-clarity/{backups,certbot/www,releases,scripts,tls}
install -d -m 0700 /opt/hutch-clarity/private
install -d -m 0700 /opt/hutch-clarity/private/signing
chown 10001:10001 /opt/hutch-clarity/private/signing

if ! id clarity-deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash clarity-deploy
fi
usermod -aG docker clarity-deploy
install -d -o clarity-deploy -g clarity-deploy -m 0700 /home/clarity-deploy/.ssh
if [[ -n ${DEPLOY_PUBLIC_KEY:-} ]]; then
  printf '%s\n' "$DEPLOY_PUBLIC_KEY" > /home/clarity-deploy/.ssh/authorized_keys
  chown clarity-deploy:clarity-deploy /home/clarity-deploy/.ssh/authorized_keys
  chmod 0600 /home/clarity-deploy/.ssh/authorized_keys
fi
chown -R clarity-deploy:clarity-deploy /opt/hutch-clarity
chown 10001:10001 /opt/hutch-clarity/private/signing

environment=/opt/hutch-clarity/.env.production
if [[ ! -f $environment ]]; then
  postgres_password=$(openssl rand -hex 24)
  keycloak_password=$(openssl rand -hex 24)
  webhook_secret=$(openssl rand -hex 32)
  subscriber_key=$(openssl rand -hex 32)
  cat > "$environment" <<EOF
REGISTRY=ghcr.io/pasidu-mihiranga
IMAGE_TAG=bootstrap
CLARITY_PROFILE=full
POSTGRES_USER=clarity
POSTGRES_PASSWORD=$postgres_password
POSTGRES_DB=clarity
DATABASE_URL=postgresql+psycopg://clarity:$postgres_password@postgres:5432/clarity
CLARITY_KAFKA_BOOTSTRAP=kafka:19092
CLARITY_HUTCH_SIM_URL=http://hutch-sim:8103
CLARITY_HUTCH_SIM_TIMEOUT=3
CLARITY_OPA_URL=http://opa:8181
KEYCLOAK_ADMIN=clarity-admin
KEYCLOAK_ADMIN_PASSWORD=$keycloak_password
CLARITY_KEYCLOAK_ISSUER=http://keycloak:8080/realms/clarity
CLARITY_KEYCLOAK_AUDIENCE=clarity-api
CLARITY_KEYCLOAK_JWKS_URL=http://keycloak:8080/realms/clarity/protocol/openid-connect/certs
CLARITY_CHANNEL_WEBHOOK_SECRET=$webhook_secret
SUBSCRIBER_HMAC_KEY=$subscriber_key
SIGNING_KEY_PATH=/run/clarity-keys/signing.pem
KEYS_DIR=/run/clarity-keys
VERIFY_BASE=https://116.203.101.73:9443/r
CLARITY_MCP_RESOURCE_URL=http://clarity-mcp:8099/mcp
CLARITY_MCP_ALLOWED_HOSTS=clarity-mcp:8099
CLARITY_MCP_API_URL=http://clarity-api:8000
OTEL_EXPORTER=none
CLARITY_LOG_FORMAT=json
AI_PREFER_TEMPLATES=true
EOF
  chmod 0600 "$environment"
  chown clarity-deploy:clarity-deploy "$environment"
fi

certificate_dir=/opt/hutch-clarity/tls
if [[ ! -f $certificate_dir/fullchain.pem ]]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
    -subj /CN=116.203.101.73 \
    -addext subjectAltName=IP:116.203.101.73 \
    -keyout "$certificate_dir/privkey.pem" \
    -out "$certificate_dir/fullchain.pem" >/dev/null 2>&1
  chmod 0600 "$certificate_dir/privkey.pem"
fi

if [[ ! -x /opt/hutch-clarity/certbot/bin/certbot ]]; then
  rm -rf /opt/hutch-clarity/certbot
  if ! python3 -m venv /opt/hutch-clarity/certbot; then
    apt-get update
    apt-get install -y --no-install-recommends python3-venv
    rm -rf /opt/hutch-clarity/certbot
    python3 -m venv /opt/hutch-clarity/certbot
  fi
  /opt/hutch-clarity/certbot/bin/pip install --disable-pip-version-check 'certbot>=5.4,<6'
fi

install -m 0644 /opt/hutch-clarity/deploy/systemd/clarity-cert-renew.service /etc/systemd/system/
install -m 0644 /opt/hutch-clarity/deploy/systemd/clarity-cert-renew.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now clarity-cert-renew.timer

ufw allow 8443/tcp
ufw allow 9443/tcp
echo "bootstrap complete; application secrets remain in $environment"

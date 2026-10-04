#!/usr/bin/env bash
set -euo pipefail

root=${CLARITY_DEPLOY_ROOT:-/opt/hutch-clarity}
certbot=/opt/hutch-clarity/certbot/bin/certbot
hook=$root/deploy/scripts/install-certificate.sh
if [[ -f /etc/letsencrypt/renewal/116.203.101.73.conf ]]; then
  "$certbot" renew --cert-name 116.203.101.73 --deploy-hook "$hook"
else
  "$certbot" certonly \
    --non-interactive --agree-tos --register-unsafely-without-email \
    --preferred-profile shortlived --webroot --webroot-path "$root/certbot/www" \
    --ip-address 116.203.101.73 --deploy-hook "$hook"
fi
"$hook"

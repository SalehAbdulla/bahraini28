#!/usr/bin/env bash
set -euo pipefail
# ---------------------------------------------------------------------------
# Bahraini 28 - copy the renewed bahraini28.com certificate into beyond's nginx
# mount and reload it.
#
# Install on the VPS as:
#   /etc/letsencrypt/renewal-hooks/deploy/bahraini28-nginx.sh   (root, +x)
#
# Deploy hooks are GLOBAL - this runs on every renewal, including beyond's and the
# social network's - so it exits quietly when our certificate is absent and never
# writes beyond's own fullchain.pem / privkey.pem.
# ---------------------------------------------------------------------------

SRC=/etc/letsencrypt/live/bahraini28.com
DST=/home/ubuntu/beyond/docker/nginx/ssl

[ -d "$SRC" ] || exit 0

cp "$SRC/fullchain.pem" "$DST/bahraini28-fullchain.pem"
cp "$SRC/privkey.pem"   "$DST/bahraini28-privkey.pem"

# 644, not the 600 certbot writes: the nginx container runs as a different uid and
# would otherwise fail with "cannot load certificate key ... Permission denied".
chmod 644 "$DST/bahraini28-fullchain.pem" "$DST/bahraini28-privkey.pem"
chown ubuntu:ubuntu "$DST/bahraini28-fullchain.pem" "$DST/bahraini28-privkey.pem"

docker exec beyond-nginx nginx -s reload 2>/dev/null || true
echo "[certbot-deploy] bahraini28 certs copied and nginx reloaded at $(date)"

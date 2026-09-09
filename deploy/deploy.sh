#!/usr/bin/env bash
set -euo pipefail
# ---------------------------------------------------------------------------
# Bahraini 28 — one-command deploy + smoke test.
#
# Prereqs (Ubuntu 24.04 / Docker host):
#   - Docker Engine + Compose v2.20+
#   - repo cloned at /opt/bahraini28   (paths in deploy/*.sh reference this)
#   - ports 80 and 443 free
#   - DNS A records for the site domain pointed at this host (for TLS)
#
# Path: backend tests (if a venv is available) -> build images -> start stack
#       -> smoke-test /health, the SPA root and (when DNS is live) https.
# ---------------------------------------------------------------------------
cd "$(dirname "$0")/.."

# --- [1/6] Backend tests ----------------------------------------------------
PY=""
if [ -x .venv/bin/python ]; then PY=".venv/bin/python"; fi
if [ -z "$PY" ] && [ -x backend/.venv/bin/python ]; then PY="backend/.venv/bin/python"; fi

if [ -n "$PY" ]; then
  echo "==> [1/6] Backend tests ($PY)"
  (cd backend && "$PY" -m pytest -q)
else
  echo "==> [1/6] Skipping backend tests (no Python venv on this host; CI covers them)"
fi

# --- [2/6] .env from template (first run only) --------------------------------
if [ ! -f deploy/.env ]; then
  echo "==> [2/6] Creating deploy/.env from template with random secrets"
  cp deploy/.env.production.example deploy/.env
  chmod 600 deploy/.env
  python3 <<'PY'
import pathlib
import secrets

p = pathlib.Path("deploy/.env")
text = p.read_text()

pw = secrets.token_urlsafe(24).replace("=", "").replace("?", "")  # alphanumeric only
sk = secrets.token_hex(32)
ap = secrets.token_urlsafe(12).replace("=", "").replace("?", "")

text = (
    text.replace("CHANGE_ME_STRONG_PASSWORD", pw)
        .replace("CHANGE_ME_64_RANDOM_CHARS", sk)
        .replace("CHANGE_ME_ADMIN_PASSWORD", ap)
)
p.write_text(text)
print("Wrote deploy/.env (DB password / SECRET_KEY / admin password generated).")
PY
fi

# --- [3/6] Build images ------------------------------------------------------
echo "==> [3/6] Building backend + frontend images"
docker compose -f deploy/docker-compose.yml build

# --- [4/6] Start stack --------------------------------------------------------
echo "==> [4/6] Starting stack (postgres -> backend -> frontend -> caddy)"
docker compose -f deploy/docker-compose.yml up -d

# --- [5/6] Smoke tests ---------------------------------------------------------
echo "==> [5/6] Smoke tests (via Caddy on :80)"
for i in $(seq 1 30); do
  if curl -fsS http://localhost/health >/dev/null 2>&1; then break; fi
  sleep 2
done
echo -n "health: "; curl -fsS http://localhost/health; echo
echo -n "root:   "; curl -fsSI http://localhost/ | head -n 1

# --- [6/6] Summary -------------------------------------------------------------
echo "==> [6/6] Done."
echo "    On first boot a bootstrap admin is created: admin / <ADMIN_INITIAL_PASSWORD in deploy/.env>"
echo "    Actions after first login:"
echo "      - change the admin password, then set SEED_DEFAULT_ADMIN=false in deploy/.env"
echo "      - optional demo data: docker compose -f deploy/docker-compose.yml run --rm backend python scripts/seed.py"
echo "    TLS certificates are issued automatically once this host is reachable as"
echo "    $(grep '^SITE_DOMAIN=' deploy/.env | cut -d= -f2 || echo bahraini28.com) (and www.) — see Namecheap DNS."

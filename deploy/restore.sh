#!/usr/bin/env bash
set -euo pipefail
# ---------------------------------------------------------------------------
# Bahraini 28 — restore a backup produced by deploy/backup.sh into the stack.
#
# Usage:
#   sudo ./restore.sh /var/backups/bahraini28/bahraini28-YYYYmmdd-HHMMSS.pgdump
# ---------------------------------------------------------------------------
APP_DIR="${BAHRAINI28_DIR:-/opt/bahraini28}"
DUMP="${1:-}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "usage: $0 <backup.pgdump>   (a file from deploy/backup.sh)" >&2
  exit 1
fi

cd "$APP_DIR"

echo "Restoring $DUMP into the running postgres container..."
docker compose -f deploy/docker-compose.yml exec -T postgres \
  sh -c 'pg_restore --clean --if-exists --exit-on-error -U "${POSTGRES_USER:-bahraini28}" -d "${POSTGRES_DB:-bahraini28}"' \
  < "$DUMP"

echo "Restore OK."
echo "Restart the backend so it reconnects cleanly:"
echo "  docker compose -f deploy/docker-compose.yml restart backend"

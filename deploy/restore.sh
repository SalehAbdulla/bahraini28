#!/usr/bin/env bash
set -euo pipefail
# ---------------------------------------------------------------------------
# Bahraini 28 — restore a backup produced by deploy/backup.sh into the stack.
#
# Usage:
#   sudo ./restore.sh <backup.pgdump> [uploads-YYYYmmdd-HHMMSS.tar.gz]
#
# The database dump is required. The matching uploads archive restores the
# receipts and business logos into the `uploads` volume — without it every
# `transactions.receipt_path` (and `businesses.logo_path`) points at a file
# that no longer exists, so a database-only restore is a *lossy* restore.
#
# Both artifacts come out of the same nightly run, so pass the pair that share
# a timestamp (from /var/backups/bahraini28 or the off-site copy).
# ---------------------------------------------------------------------------
APP_DIR="${BAHRAINI28_DIR:-/opt/bahraini28}"
DUMP="${1:-}"
UPLOADS="${2:-}"
VOLUME="${UPLOADS_VOLUME:-bahraini28_uploads}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "usage: $0 <backup.pgdump> [uploads-YYYYmmdd-HHMMSS.tar.gz]" >&2
  echo "       (artifacts come from deploy/backup.sh, or from off-site storage)" >&2
  exit 1
fi

cd "$APP_DIR"

echo "Restoring $DUMP into the running postgres container..."
docker compose -f deploy/docker-compose.yml exec -T postgres \
  sh -c 'pg_restore --clean --if-exists --exit-on-error -U "${POSTGRES_USER:-bahraini28}" -d "${POSTGRES_DB:-bahraini28}"' \
  < "$DUMP"
echo "Database restore OK."

if [ -n "$UPLOADS" ]; then
  if [ ! -f "$UPLOADS" ]; then
    echo "error: uploads archive '$UPLOADS' not found" >&2
    exit 1
  fi
  echo "Restoring $(basename "$UPLOADS") into the '$VOLUME' volume..."
  # Extract *over* the existing volume rather than wiping it: after a volume
  # loss the volume is empty (so this is an exact restore), and after a partial
  # recovery it cannot destroy files that are still referenced.
  UPLOADS_DIR="$(cd "$(dirname "$UPLOADS")" && pwd)"
  docker run --rm \
    -v "$VOLUME":/data \
    -v "$UPLOADS_DIR":/backup:ro \
    alpine:3 \
    tar xzf "/backup/$(basename "$UPLOADS")" -C /data
  echo "Uploads restore OK (receipts + logos)."
else
  echo "WARNING: no uploads archive given — receipts and logos will 404."
  echo "         Re-run with the matching uploads-<stamp>.tar.gz from the same"
  echo "         backup run (the two artifacts share a timestamp)."
fi

echo "Restart the backend so it reconnects cleanly:"
echo "  docker compose -f deploy/docker-compose.yml restart backend"


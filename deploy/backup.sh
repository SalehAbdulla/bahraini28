#!/usr/bin/env bash
set -euo pipefail
# ---------------------------------------------------------------------------
# Bahraini 28 — daily backup (PostgreSQL dump + uploads volume).
#
# Expected clone location: /opt/bahraini28  (set BAHRAINI28_DIR to override).
# Output: /var/backups/bahraini28/  (set BACKUP_DIR to override).
# Retention: BACKUP_KEEP_DAYS (default 14).
#
# Install as root (see deploy/backup-cron.txt):
#   sudo mkdir -p /opt/bahraini28 /var/backups/bahraini28
#   sudo cp deploy/backup.sh /usr/local/bin/bahraini28-backup
#   sudo chmod +x /usr/local/bin/bahraini28-backup
# Then add a cron entry (crontab -e as root) with the line from backup-cron.txt.
# ---------------------------------------------------------------------------
APP_DIR="${BAHRAINI28_DIR:-/opt/bahraini28}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/bahraini28}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
cd "$APP_DIR"

echo "[$(date -Is)] Dumping PostgreSQL..."
docker compose -f deploy/docker-compose.yml exec -T postgres \
  sh -c 'pg_dump -U "${POSTGRES_USER:-bahraini28}" -d "${POSTGRES_DB:-bahraini28}" -Fc' \
  > "$BACKUP_DIR/bahraini28-$STAMP.pgdump"

echo "[$(date -Is)] Archiving uploads volume..."
docker run --rm \
  -v bahraini28_uploads:/data:ro \
  -v "$BACKUP_DIR":/backup \
  alpine:3 \
  tar czf "/backup/uploads-$STAMP.tar.gz" -C /data .

echo "[$(date -Is)] Retention: keeping $KEEP_DAYS days"
find "$BACKUP_DIR" -name 'bahraini28-*.pgdump' -mtime "+$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'uploads-*.tar.gz' -mtime "+$KEEP_DAYS" -delete

echo "[$(date -Is)] Backup complete:"
ls -lh "$BACKUP_DIR"

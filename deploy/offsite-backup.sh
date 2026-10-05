#!/usr/bin/env bash
set -euo pipefail
# ---------------------------------------------------------------------------
# Bahraini 28 — copy the backups OFF this host (object storage).
#
# deploy/backup.sh writes the PostgreSQL dump and the uploads archive to
# BACKUP_DIR *on this machine*. If the VPS is lost, so is every backup of it,
# which is the single biggest risk in the current setup. This script mirrors
# those artifacts somewhere else:
#
#     deploy/backup.sh  ->  BACKUP_DIR (local, 14-day retention)
#                       ->  rclone  ->  OFFSITE_REMOTE (off-site, versioned)
#
# It uses `rclone copy`, never `rclone sync`: a mirror must never be able to
# *delete* the remote because a local path was mistyped or a disk mount was
# missing. Prune the remote with a bucket lifecycle rule instead (see below).
#
# Usage:
#   ./offsite-backup.sh [--dry-run]
#
# Configuration — deploy/offsite.env (copy the .example), or the environment:
#   OFFSITE_REMOTE=oci:bahraini28-backups    # ANY rclone destination
#   RCLONE_CONFIG=/root/.config/rclone/rclone.conf   # optional
#
#   OFFSITE_REMOTE also accepts a plain local path (e.g. a mounted USB disk or
#   an NFS share), which is what the test suite uses.
#
# Install (see deploy/backup-cron.txt):
#   sudo cp deploy/offsite-backup.sh /usr/local/bin/bahraini28-offsite-backup
#   sudo chmod +x /usr/local/bin/bahraini28-offsite-backup
#
# Recommended off-site retention (set it on the bucket, not here):
#   * keep dailies for 30 days, monthlies for 12 months (lifecycle rule);
#   * enable object versioning + a delete-protection/object-lock policy so a
#     compromised host cannot wipe the history it is backing up.
# ---------------------------------------------------------------------------

APP_DIR="${BAHRAINI28_DIR:-/opt/bahraini28}"
OFFSITE_ENV="${OFFSITE_ENV:-$APP_DIR/deploy/offsite.env}"

# Precedence: explicit environment > deploy/offsite.env > built-in defaults.
if [ -f "$OFFSITE_ENV" ]; then
  # shellcheck disable=SC1090
  _keep_remote="${OFFSITE_REMOTE:-}"
  _keep_dir="${BACKUP_DIR:-}"
  _keep_rclone_cfg="${RCLONE_CONFIG:-}"
  set -a
  . "$OFFSITE_ENV"
  set +a
  [ -n "$_keep_remote" ] && OFFSITE_REMOTE="$_keep_remote"
  [ -n "$_keep_dir" ] && BACKUP_DIR="$_keep_dir"
  [ -n "$_keep_rclone_cfg" ] && RCLONE_CONFIG="$_keep_rclone_cfg"
fi

OFFSITE_REMOTE="${OFFSITE_REMOTE:-}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/bahraini28}"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "error: unknown argument '$arg' (try --help)" >&2; exit 2 ;;
  esac
done

die() {
  echo "error: $*" >&2
  exit 1
}

# `date -Is` is a GNU extension — BSD/macOS `date` rejects it and prints an error
# instead of a timestamp. Build the ISO-8601 UTC stamp from the portable form.
iso8601() { date -u +%Y-%m-%dT%H:%M:%SZ; }

echo "[$(iso8601)] Off-site backup starting"

command -v rclone >/dev/null 2>&1 || die \
  "'rclone' is not installed. Install it (https://rclone.org/install/), run
         'rclone config' to add the remote, then retry."

[ -n "$OFFSITE_REMOTE" ] || die \
  "OFFSITE_REMOTE is not set. Copy deploy/offsite.env.example to
         deploy/offsite.env and point it at your bucket — without it the
         backups never leave this host."

[ -d "$BACKUP_DIR" ] || die \
  "backup directory '$BACKUP_DIR' does not exist (has deploy/backup.sh run yet?)"

shopt -s nullglob
artifacts=("$BACKUP_DIR"/bahraini28-*.pgdump "$BACKUP_DIR"/uploads-*.tar.gz)
shopt -u nullglob
[ "${#artifacts[@]}" -gt 0 ] || die \
  "no backup artifacts found in '$BACKUP_DIR' (has deploy/backup.sh run yet?)"

LOCAL_BYTES="$(du -ck "${artifacts[@]}" | tail -1 | cut -f1)"
echo "  local  : ${#artifacts[@]} artifact(s), $((LOCAL_BYTES / 1024)) MiB in $BACKUP_DIR"
echo "  remote : $OFFSITE_REMOTE"

rclone_args=(
  copy "$BACKUP_DIR" "$OFFSITE_REMOTE"
  # Only our own artifacts: never ship a stray file that happens to be in the
  # directory (a half-written dump, an operator's scratch note, ...).
  --include "bahraini28-*.pgdump"
  --include "uploads-*.tar.gz"
  --log-level INFO
  --stats-one-line
)
if [ "$DRY_RUN" = 1 ]; then
  rclone_args+=(--dry-run)
  echo "  mode   : DRY RUN (nothing will be uploaded)"
fi

if ! rclone "${rclone_args[@]}"; then
  # Exit non-zero so cron records a failure instead of a silent no-op.
  die "rclone copy to '$OFFSITE_REMOTE' failed"
fi

if [ "$DRY_RUN" = 1 ]; then
  echo "[$(iso8601)] Dry run complete — nothing was uploaded."
else
  echo "[$(iso8601)] Off-site copy complete ($OFFSITE_REMOTE)"
fi

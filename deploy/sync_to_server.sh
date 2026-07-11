#!/usr/bin/env bash
set -euo pipefail

SERVER="${1:-}"
REMOTE_DIR="${REMOTE_DIR:-/opt/lumenalpha}"

if [[ -z "$SERVER" ]]; then
  echo "Usage: bash deploy/sync_to_server.sh root@8.153.88.170" >&2
  exit 1
fi

ssh "$SERVER" "mkdir -p '$REMOTE_DIR'"
RSYNC_EXCLUDES=(
  --exclude ".git/" \
  --exclude ".DS_Store" \
  --exclude ".cache/" \
  --exclude ".env" \
  --exclude ".env.*" \
  --exclude ".venv*/" \
  --exclude "node_modules/" \
  --exclude "__pycache__/" \
  --exclude "backups/" \
  --exclude "data/*.sqlite*" \
  --exclude "data/sector_rotation/cache/" \
  --exclude "data/sector_rotation/daily_runs/" \
  --exclude "data/sector_rotation/ai_analysis/"
)

if [[ "${SYNC_DATA:-0}" != "1" ]]; then
  RSYNC_EXCLUDES+=(
    --exclude "data/"
    --exclude "web/sector_rotation_dashboard/dashboard_data.js"
    --exclude "web/sector_rotation_dashboard/daily_analysis.md"
  )
fi

rsync -az --delete "${RSYNC_EXCLUDES[@]}" ./ "$SERVER:$REMOTE_DIR/"

echo "Synced project to $SERVER:$REMOTE_DIR"

#!/bin/sh
# Nightly backup of pocpod0's named Docker volumes on the VPS.
# Installed via `make vps-backup-schedule` (cron: 03:00 daily).
# Mirrors the Makefile's `vps-backup` target; kept in sync manually if that changes.
set -e

VPS_PATH=/home/nicolas/pocpod0
cd "$VPS_PATH"
mkdir -p backups
DATE=$(date +%F)

for VOL in pocpod0_css-data pocpod0_openclaw-data-default pocpod0_oxigraph-data pocpod0_qdrant-data; do
  NAME=${VOL#pocpod0_}
  docker run --rm -v "$VOL":/data alpine tar czf - /data > "backups/$NAME-$DATE.tar.gz"
done

# 7-day retention
find backups -name '*.tar.gz' -mtime +7 -delete

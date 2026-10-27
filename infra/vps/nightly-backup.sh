#!/bin/sh
# Nightly backup of pocpod0's named Docker volumes on the VPS.
# Installed via `make vps-backup-schedule` (cron: 03:00 daily) as
# /usr/local/sbin/pocpod0-backup, root-owned.
# Mirrors the Makefile's `vps-backup` target; kept in sync manually if that changes.
#
# Until 2026-10-25 the cron ran a copy in $VPS_PATH/backups/. That copy
# vanished the day after it was installed (2026-07-22) and the cron logged
# "not found" every night for three months, unnoticed: no nightly backup ever
# ran. The copy now lives outside the synced tree, and every run says how it
# went in the journal (journalctl -t pocpod0-backup).
set -eu
# The archives hold every pod's data: readable by root only. Until 2026-10-25
# they were 644 in a directory any local user can list.
umask 077

VPS_PATH=/home/nicolas/pocpod0
cd "$VPS_PATH"
mkdir -p backups
DATE=$(date +%F)

fail() { logger -t pocpod0-backup -p user.err "FAILED: $*"; echo "FAILED: $*" >&2; exit 1; }

# pod.nicolasdb.eu's data lives in the instance's volumes (nicolasdb-pods_*,
# /srv/nicolasdb-pods) since the cutover to solid-css-overlay's image; the
# archive names stay css-data-<date> so the series continues. Qdrant is retired.
for VOL in nicolasdb-pods_css-data nicolasdb-pods_mcp-audit pocpod0_openclaw-data-default pocpod0_oxigraph-data; do
  # The volume must exist: `docker run -v` would create an empty one and
  # archive nothing, which then reads as a backup.
  docker volume inspect "$VOL" >/dev/null 2>&1 || fail "no volume $VOL"
  NAME=${VOL#*_}
  OUT="backups/$NAME-$DATE.tar.gz"
  # Written to a temp name and checked before it counts: a half-written
  # archive must never look like a backup, nor let the retention below
  # delete the last good one.
  docker run --rm -v "$VOL":/data:ro alpine tar czf - /data > "$OUT.part" || fail "tar $VOL"
  gzip -t "$OUT.part" || fail "gzip check $OUT"
  mv "$OUT.part" "$OUT"
done

# 7-day retention, only after every volume above succeeded (set -e), and only
# for the nightly archives at the top of backups/ (older manual sets live in
# subfolders and are kept).
find backups -maxdepth 1 -name '*.tar.gz' -mtime +7 -delete

logger -t pocpod0-backup "ok: $(du -ch backups/*-"$DATE".tar.gz | tail -1 | cut -f1) for $DATE"

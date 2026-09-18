#!/usr/bin/env bash
# pg_dump into ./backups, newest 30 kept. Run by release.sh before every
# deploy, and worth putting on a daily cron as well — see the README.
set -euo pipefail

# A deploy must not depend on whatever PATH it inherits: cron supplies a minimal
# one, and an interactive shell can have anything shadowing the coreutils this
# script relies on. Pin it.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

APP_DIR="$(cd "${0%/*}" 2>/dev/null && pwd || pwd)"
cd "$APP_DIR"

KEEP=30
DEST="$APP_DIR/backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$DEST/enxoval-${STAMP}.sql.gz"

mkdir -p "$DEST"

if ! docker compose -f docker-compose.prod.yml ps -q db | grep -q .; then
	echo "database container is not running; nothing to back up"
	exit 0
fi

# Straight to a temp name so an interrupted dump is never mistaken for a good one.
docker compose -f docker-compose.prod.yml exec -T db \
	pg_dump -U enxoval -d enxoval --clean --if-exists |
	gzip >"${FILE}.partial"
mv "${FILE}.partial" "$FILE"

echo "backup written: $FILE ($(du -h "$FILE" | cut -f1))"

# Keep the newest $KEEP, delete the rest.
ls -1t "$DEST"/enxoval-*.sql.gz 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r old; do
	rm -f -- "$old"
	echo "pruned old backup: $(basename "$old")"
done

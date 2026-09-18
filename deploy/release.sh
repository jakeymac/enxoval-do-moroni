#!/usr/bin/env bash
# Rolls the VM forward to one image tag, and back again if it does not come up.
# Called by .github/workflows/deploy.yml over SSH:  ./release.sh <image-tag>
set -euo pipefail

# A deploy must not depend on whatever PATH it inherits: cron supplies a minimal
# one, and an interactive shell can have anything shadowing the coreutils this
# script relies on. Pin it.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

TAG="${1:?usage: release.sh <image-tag>}"
APP_DIR="$(cd "${0%/*}" 2>/dev/null && pwd || pwd)"
cd "$APP_DIR"

compose() { docker compose -f docker-compose.prod.yml "$@"; }

set_env() { # set_env KEY VALUE — rewrite in place, or append if absent
	# awk rather than `sed -i`: the in-place flag takes an argument on BSD and
	# not on GNU, so a sed version of this silently corrupts .env on a Mac.
	# Lines other than the key are reprinted byte for byte, so secrets
	# containing '=' survive untouched.
	local key="$1" value="$2" tmp
	tmp="$(mktemp)"
	if grep -qE "^${key}=" .env; then
		awk -v k="$key" -v v="$value" '$0 ~ "^" k "=" { print k "=" v; next } { print }' \
			.env >"$tmp"
	else
		cat .env >"$tmp"
		printf '%s=%s\n' "$key" "$value" >>"$tmp"
	fi
	# Copy the contents back rather than mv, to keep the original's mode and owner.
	cat "$tmp" >.env
	rm -f "$tmp"
}

wait_for_health() { # wait_for_health SECONDS
	local deadline=$((SECONDS + $1)) id status state restarts
	id="$(compose ps -q web)"
	[ -n "$id" ] || { echo "no web container"; return 1; }
	while [ "$SECONDS" -lt "$deadline" ]; do
		state="$(docker inspect --format '{{.State.Status}}' "$id" 2>/dev/null || echo gone)"
		restarts="$(docker inspect --format '{{.RestartCount}}' "$id" 2>/dev/null || echo 0)"

		# `restart: unless-stopped` means a container that dies on startup —
		# a failed migration, most likely — flaps instead of staying exited.
		# Waiting out the full timeout on an obvious crash loop wastes minutes.
		if [ "$restarts" -ge 3 ]; then
			echo "container has restarted ${restarts} times; treating as failed"
			return 1
		fi
		case "$state" in
		running | restarting | created) ;;
		*)
			echo "container is '${state}', not running"
			return 1
			;;
		esac

		status="$(docker inspect \
			--format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
			"$id" 2>/dev/null || echo none)"
		case "$status" in
		healthy) return 0 ;;
		unhealthy)
			echo "container reported unhealthy"
			return 1
			;;
		esac
		sleep 3
	done
	echo "timed out after $1s waiting for the app to become healthy"
	return 1
}

previous="$(grep -E '^IMAGE_TAG=' .env | cut -d= -f2- || true)"
echo "==> releasing ${TAG} (current: ${previous:-none})"

# A failed migration is the one thing here that a tag rollback cannot undo, so
# take the dump first and refuse to deploy without one.
echo "==> backing up the database"
./backup.sh

echo "==> pulling the image"
set_env IMAGE_TAG "$TAG"
compose pull web

echo "==> starting the database"
compose up -d db

# The entrypoint runs `manage.py migrate` before gunicorn starts.
echo "==> starting the app (runs migrations)"
compose up -d web

if wait_for_health 180; then
	echo "==> healthy; bringing up the proxy"
	compose up -d caddy
	compose ps
	docker image prune -f --filter "until=168h" >/dev/null 2>&1 || true
	echo "==> released ${TAG}"
	exit 0
fi

echo "!!! ${TAG} did not come up; recent logs:"
compose logs --tail 60 web || true

if [ -z "$previous" ] || [ "$previous" = "$TAG" ]; then
	echo "!!! no previous tag to fall back to — leaving it stopped for inspection"
	exit 1
fi

echo "==> rolling back to ${previous}"
set_env IMAGE_TAG "$previous"
compose up -d web
if wait_for_health 120; then
	compose up -d caddy
	echo "!!! rolled back to ${previous}. NOTE: a migration that already ran is"
	echo "!!! still applied — check the backup in ./backups if the schema moved."
else
	echo "!!! rollback also failed; the site is down and needs a look"
fi
exit 1

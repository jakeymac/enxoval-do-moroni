#!/usr/bin/env bash
# One-time setup for a fresh Debian/Ubuntu Google Cloud VM.
# Copy this file to the VM and run it with sudo:
#   sudo bash bootstrap-vm.sh <linux-user>
set -euo pipefail

DEPLOY_USER="${1:?usage: sudo bash bootstrap-vm.sh <linux-user>}"
APP_DIR=/opt/enxoval

id "$DEPLOY_USER" >/dev/null 2>&1 || { echo "no such user: $DEPLOY_USER"; exit 1; }

echo "==> installing docker"
if ! command -v docker >/dev/null 2>&1; then
	apt-get update -qq
	apt-get install -y -qq ca-certificates curl
	install -m 0755 -d /etc/apt/keyrings
	# Ubuntu images report ubuntu in ID; Debian reports debian. The repo path differs.
	distro="$(. /etc/os-release && echo "$ID")"
	codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
	curl -fsSL "https://download.docker.com/linux/${distro}/gpg" -o /etc/apt/keyrings/docker.asc
	chmod a+r /etc/apt/keyrings/docker.asc
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${distro} ${codename} stable" \
		>/etc/apt/sources.list.d/docker.list
	apt-get update -qq
	apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

echo "==> letting ${DEPLOY_USER} drive docker without sudo"
usermod -aG docker "$DEPLOY_USER"

echo "==> creating ${APP_DIR}"
mkdir -p "$APP_DIR/backups"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"

echo "==> enabling docker at boot"
systemctl enable --now docker

echo "==> nightly database backup at 03:20"
cat >/etc/cron.d/enxoval-backup <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
20 3 * * * ${DEPLOY_USER} ${APP_DIR}/backup.sh >> ${APP_DIR}/backups/cron.log 2>&1
CRON
chmod 0644 /etc/cron.d/enxoval-backup

cat <<DONE

Done. Still to do, as ${DEPLOY_USER} (not root):

  1. Copy deploy/ onto the VM:
       docker-compose.prod.yml  Caddyfile  release.sh  backup.sh
     into ${APP_DIR}/ , and make the scripts executable.

  2. Create ${APP_DIR}/.env from env.example and fill it in.

  3. Log in to GHCR once, so the VM can pull private images:
       docker login ghcr.io -u <github-user>
     Use a fine-grained token with only read:packages. The credentials
     persist in ~/.docker/config.json, so deploys never carry a token.

  4. First release:
       ${APP_DIR}/release.sh latest

  5. Create the owner account:
       cd ${APP_DIR} && docker compose -f docker-compose.prod.yml \\
         exec web python manage.py createsuperuser

  Log out and back in first — group membership only applies to new sessions.
DONE

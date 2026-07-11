#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/lumenalpha}"
APP_USER="${APP_USER:-lumenalpha}"
DOMAIN="${DOMAIN:-lumenalpha.xyz}"

if [[ "$(id -u)" != "0" ]]; then
  echo "Run as root: sudo bash deploy/bootstrap_ubuntu.sh" >&2
  exit 1
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "Missing $APP_DIR. Upload the project there before running this script." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y build-essential ca-certificates curl gnupg nginx python3 python3-venv python3-pip rsync sqlite3 certbot python3-certbot-nginx

if ! command -v node >/dev/null 2>&1 || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 18 ? 0 : 1)' >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

timedatectl set-timezone Asia/Shanghai

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip wheel
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

cd "$APP_DIR/web/sector_rotation_dashboard"
if [[ -f package-lock.json ]]; then
  npm ci --omit=dev
else
  npm install --omit=dev
fi

if [[ ! -f "$APP_DIR/.env.local" ]]; then
  install -m 0600 -o "$APP_USER" -g "$APP_USER" "$APP_DIR/deploy/env.example" "$APP_DIR/.env.local"
fi

install -m 0644 "$APP_DIR/deploy/lumenalpha-web.service" /etc/systemd/system/lumenalpha-web.service
install -m 0644 "$APP_DIR/deploy/lumenalpha-refresh.service" /etc/systemd/system/lumenalpha-refresh.service
install -m 0644 "$APP_DIR/deploy/lumenalpha-refresh.timer" /etc/systemd/system/lumenalpha-refresh.timer

install -m 0644 "$APP_DIR/deploy/nginx-lumenalpha.conf" /etc/nginx/sites-available/lumenalpha.conf
sed -i "s/server_name .*/server_name ${DOMAIN} www.${DOMAIN} _;/" /etc/nginx/sites-available/lumenalpha.conf
ln -sf /etc/nginx/sites-available/lumenalpha.conf /etc/nginx/sites-enabled/lumenalpha.conf
rm -f /etc/nginx/sites-enabled/default

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

systemctl daemon-reload
systemctl enable --now lumenalpha-web.service
systemctl enable --now lumenalpha-refresh.timer
nginx -t
systemctl reload nginx

echo
echo "Deployment bootstrap complete."
echo "Web service:    systemctl status lumenalpha-web --no-pager"
echo "Refresh timer:  systemctl list-timers lumenalpha-refresh.timer"
echo "HTTP check:     curl -I http://127.0.0.1"
echo "HTTPS after ICP/DNS: certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"

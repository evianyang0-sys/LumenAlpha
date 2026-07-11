# LumenAlpha Production Deployment

Target server: Ubuntu 22.04/24.04.

## 1. Open Security Group

Allow inbound:

- TCP 22 for SSH. Prefer your own IP only.
- TCP 80 for HTTP.
- TCP 443 for HTTPS.

## 2. Upload Project

From this repo on your Mac:

```bash
SYNC_DATA=1 bash deploy/sync_to_server.sh root@8.153.88.170
```

`SYNC_DATA=1` is only for the initial upload. Normal code updates omit it so local snapshots cannot overwrite newer production data.

If SSH key login is not configured yet, upload the project another way, but keep the remote path:

```text
/opt/lumenalpha
```

Do not upload `.env.local` from your Mac.

## 3. Create Server Secret File

On the server:

```bash
cd /opt/lumenalpha
cp deploy/env.example .env.local
nano .env.local
```

Fill only on the server:

```text
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-v4-pro
HOST=127.0.0.1
PORT=8766
USER_DB_PATH=/opt/lumenalpha/data/lumenalpha_users.sqlite
```

Do not use `NODE_TLS_REJECT_UNAUTHORIZED=0` in production unless a server-side proxy forces it.

## 4. Bootstrap Server

On the server:

```bash
cd /opt/lumenalpha
bash deploy/bootstrap_ubuntu.sh
```

This installs Node 20, Python venv dependencies, Nginx, systemd services, and a daily 21:00 Asia/Shanghai refresh timer.

## 5. Verify

```bash
systemctl status lumenalpha-web --no-pager
systemctl list-timers lumenalpha-refresh.timer
curl -I http://127.0.0.1
curl -I http://8.153.88.170
```

Run one refresh manually:

```bash
systemctl start lumenalpha-refresh.service
journalctl -u lumenalpha-refresh.service -n 120 --no-pager
```

## 6. Domain And HTTPS

After ICP filing is approved, point DNS A records to the server IP:

```text
lumenalpha.xyz      -> 8.153.88.170
www.lumenalpha.xyz  -> 8.153.88.170
```

Then on the server:

```bash
certbot --nginx -d lumenalpha.xyz -d www.lumenalpha.xyz
```

Public registration and login stay disabled on plain HTTP. They become available automatically after Nginx serves the site through HTTPS.

## 7. User Database

User accounts, sessions, and watchlists are stored in:

```text
/opt/lumenalpha/data/lumenalpha_users.sqlite
```

Stock and analysis datasets remain file-based under `/opt/lumenalpha/data`. Back up the user database before deployments that change account storage:

```bash
mkdir -p /opt/lumenalpha/backups
sqlite3 /opt/lumenalpha/data/lumenalpha_users.sqlite ".backup '/opt/lumenalpha/backups/users.sqlite'"
```

## 8. Useful Commands

Restart web service:

```bash
systemctl restart lumenalpha-web
```

View web logs:

```bash
journalctl -u lumenalpha-web -n 120 --no-pager
```

View refresh logs:

```bash
journalctl -u lumenalpha-refresh.service -n 120 --no-pager
```

Update code after local changes:

```bash
bash deploy/sync_to_server.sh root@8.153.88.170
ssh root@8.153.88.170 'chown -R lumenalpha:lumenalpha /opt/lumenalpha && systemctl restart lumenalpha-web'
```

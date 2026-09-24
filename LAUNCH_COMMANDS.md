# Launch Commands — Docker on a Linux server

Deploying the PBO Regulatory Authority ICT portal (maintenance reports + help desk)
with Docker Compose. The stack is two containers:

| Service | Image | Purpose |
| --- | --- | --- |
| `db` | `postgres:16-alpine` | PostgreSQL, data on the named volume `postgres_data` |
| `web` | built from `Dockerfile` | Flask + Socket.IO under gunicorn on port 5000 |

`entrypoint.sh` runs `db upgrade` then `seed-data` on **every** container start, so
migrations and seeding are automatic — you never run them by hand for a normal deploy.

---

## 0. Before the first deploy

**`.env` is not in the repository** (it is gitignored, and it must stay that way — it
holds the Gmail app password, the database password and `SECRET_KEY`). You create it on
the server once, by hand. Nothing else in this guide will work without it.

Check the server has what it needs:

```bash
docker --version
docker compose version        # needs Compose v2 — "docker-compose" v1 is not supported
```

If Docker is not installed (Ubuntu/Debian):

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"     # log out and back in for this to take effect
```

---

## 1. Get the code onto the server

```bash
sudo mkdir -p /opt/pbora-ict
sudo chown "$USER":"$USER" /opt/pbora-ict
git clone <your-repo-url> /opt/pbora-ict
cd /opt/pbora-ict
```

---

## 2. Create `.env`

```bash
cd /opt/pbora-ict
umask 077          # so the file is not world-readable
nano .env
```

Paste this and **replace every `CHANGE_ME`**. Do not put quotes around the values —
they are read both by Compose's variable substitution and by the container.

```ini
FLASK_ENV=production

# Generate with:  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=CHANGE_ME

# Seeded accounts. Change these from the shared default before going live.
ADMIN_USERNAME=jonyango
ADMIN_PASSWORD=CHANGE_ME
DEFAULT_USER_PASSWORD=CHANGE_ME
HELPDESK_MANAGER_USERNAME=ictmanager
HELPDESK_MANAGER_PASSWORD=CHANGE_ME
HELPDESK_OFFICER_USERNAME=icthelpdesk
HELPDESK_OFFICER_PASSWORD=CHANGE_ME

# Database. Compose builds the container's DATABASE_URL from these three and
# points it at the `db` service, so you do not set DATABASE_URL here.
POSTGRES_DB=pbora_ict
POSTGRES_USER=pbora
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_HOST_PORT=5433

# Email. MAIL_PASSWORD is a Gmail *app password*, not the account password.
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=CHANGE_ME
MAIL_PASSWORD=CHANGE_ME
MAIL_SENDER_NAME=PBORA
MAIL_DEFAULT_SENDER=CHANGE_ME

# Who hears about submitted reports and newly created accounts.
NOTIFY_EMAILS=jonyango@pbora.go.ke
ADMIN_EMAIL=jonyango@pbora.go.ke

# How long a signup confirmation link stays valid, in seconds (default 72h).
EMAIL_CONFIRM_MAX_AGE=259200
```

Lock it down:

```bash
chmod 600 .env
```

---

## 3. First launch

> **The short way.** Once `.env` exists and `cloudflared tunnel login` has been run,
> `./LAUNCH_MAINTENANCE.sh` does everything in sections 3 and 9 in one command — builds
> the stack, waits for it, creates the tunnel, points `maintenance.harolditdata.uk` at
> it, installs cloudflared as a systemd service and verifies the public URL. It is
> idempotent, so it is also the normal way to deploy an update. See section 12.
> The rest of this section is the manual equivalent.

```bash
cd /opt/pbora-ict
docker compose build
docker compose up -d
docker compose logs -f web        # Ctrl-C to stop following
```

You are looking for the migrations running, then gunicorn binding:

```
INFO  [alembic.runtime.migration] Running upgrade ... -> d1a7f2b9c6e4, self-signup email confirmation
[INFO] Listening at: http://0.0.0.0:5000
```

Confirm it answers:

```bash
curl -I http://localhost:5000/login        # expect: HTTP/1.1 200 OK
curl -I http://localhost:5000/             # expect: HTTP/1.1 302 FOUND -> /login
```

The `302` on `/` is correct — the portal is gated, so signed-out visitors are sent to
the sign-in page.

---

## 4. Everyday commands

```bash
cd /opt/pbora-ict

docker compose ps                 # what is running
docker compose logs -f web        # follow app logs
docker compose logs -f db         # follow database logs
docker compose logs --tail=200 web
docker compose restart web        # restart the app only
docker compose stop               # stop, keep the data
docker compose start              # start again
docker compose down               # stop and remove containers (volume survives)
```

> `docker compose down -v` also deletes the `postgres_data` volume and **destroys every
> report, ticket and account**. Do not use it unless that is what you want.

---

## 5. Deploying an update

```bash
cd /opt/pbora-ict
git pull
docker compose build web
docker compose up -d web
docker compose logs -f web
```

`entrypoint.sh` applies any new migration on start, so a schema change needs no extra
step. Take a backup first (section 7) whenever the release contains one.

---

## 6. Running commands inside the container

```bash
# Apply migrations by hand (normally automatic)
docker compose exec web flask --app 'app:create_app()' db upgrade

# Current migration revision
docker compose exec web flask --app 'app:create_app()' db current

# Re-run seeding (idempotent: it will not duplicate anything)
docker compose exec web flask --app 'app:create_app()' seed-data

# A shell in the app container
docker compose exec web sh

# A psql prompt on the database
docker compose exec db psql -U "$(grep ^POSTGRES_USER .env | cut -d= -f2)" \
                            -d "$(grep ^POSTGRES_DB .env | cut -d= -f2)"
```

List the accounts that exist:

```bash
docker compose exec db psql -U "$(grep ^POSTGRES_USER .env | cut -d= -f2)" \
  -d "$(grep ^POSTGRES_DB .env | cut -d= -f2)" \
  -c "select id, username, email, is_admin, helpdesk_role, is_active, self_registered, email_confirmed_at from users order by id;"
```

---

## 7. Backup and restore

Back up before every update. The dump is plain SQL and compresses well.

```bash
cd /opt/pbora-ict
mkdir -p backups

docker compose exec -T db pg_dump \
  -U "$(grep ^POSTGRES_USER .env | cut -d= -f2)" \
  -d "$(grep ^POSTGRES_DB .env | cut -d= -f2)" \
  | gzip > "backups/pbora-$(date +%Y%m%d-%H%M%S).sql.gz"
```

Restore into an empty database:

```bash
gunzip -c backups/pbora-YYYYMMDD-HHMMSS.sql.gz | \
docker compose exec -T db psql \
  -U "$(grep ^POSTGRES_USER .env | cut -d= -f2)" \
  -d "$(grep ^POSTGRES_DB .env | cut -d= -f2)"
```

A nightly backup at 02:00 (`crontab -e`):

```cron
0 2 * * * cd /opt/pbora-ict && docker compose exec -T db pg_dump -U pbora -d pbora_ict | gzip > backups/pbora-$(date +\%Y\%m\%d).sql.gz
```

---

## 8. Rolling back a bad release

```bash
cd /opt/pbora-ict
git log --oneline -5
git checkout <previous-good-commit>
docker compose build web
docker compose up -d web
```

If the bad release added a migration, step the schema back **before** rolling the code
back — the old code will not understand the new schema:

```bash
docker compose exec web flask --app 'app:create_app()' db downgrade
```

---

## 9. Putting it on the internet

The container listens on port 5000. Do not expose that directly — terminate TLS in
front of it. Nginx on the host:

```nginx
server {
    listen 80;
    server_name ict.pbora.go.ke;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # The help desk pushes live ticket updates over WebSockets.
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }
}
```

```bash
sudo certbot --nginx -d ict.pbora.go.ke      # TLS certificate
sudo ufw allow 80,443/tcp
sudo ufw deny 5000/tcp                        # app reachable only through nginx
```

The WebSocket headers are not optional — without them the help desk dashboard silently
stops receiving live ticket updates.

---

## 10. Troubleshooting

**`web` restarts in a loop.** Almost always the database was not ready or `.env` is
wrong. `docker compose logs web` shows the real error. Check `db` is healthy with
`docker compose ps`.

**`FATAL: password authentication failed`.** `POSTGRES_PASSWORD` in `.env` no longer
matches the password baked into the existing volume — Postgres only reads it when the
volume is first created. Either restore the old password, or drop the volume
(`docker compose down -v`, **destroys the data**) and restore from a backup.

**No email arriving.** `MAIL_PASSWORD` must be a Gmail **app password** (16 characters,
2FA enabled on the account), not the account password. Mail failures are swallowed by
design so a submission is never lost — look for `Could not send` in
`docker compose logs web`.

**Signup says the link is invalid.** The link has expired (`EMAIL_CONFIRM_MAX_AGE`), or
`SECRET_KEY` changed after the email was sent — the token is signed with it. Use
`/confirm/resend`.

**Everything redirects to `/login`.** Working as designed: the whole portal is gated.
Only `/login`, `/signup`, `/confirm/...` and the help desk intake (`/helpdesk/`,
`/helpdesk/track`) are public.

**Port 5000 already taken.** Change the published port in `docker-compose.yml` to
e.g. `"5001:5000"` and update the nginx `proxy_pass`.

---

## 11. Notes specific to this deployment

**Do not run `deploy.sh` on the Docker server.** It is the bare-metal installer, and it
*rewrites* `.env` from scratch — dropping `MAIL_*`, `NOTIFY_EMAILS`, `ADMIN_EMAIL`,
`HELPDESK_*_PASSWORD` and `EMAIL_CONFIRM_MAX_AGE`. Confirmation and notification email
would stop working. Use the Compose commands above instead.

**PostgreSQL version.** Compose pins `postgres:16-alpine`, while the current development
database is PostgreSQL 18. A fresh deploy is fine. But a dump taken from 18 **cannot** be
restored into 16 — `pg_dump` output only loads into an equal or newer server. If you are
carrying the existing data across, first change the image in `docker-compose.yml` to
`postgres:18-alpine`, then deploy.

**First sign-in.** Seeded accounts are `jonyango` (administrator), `ictmanager` and
`icthelpdesk`, each with the password you set in `.env`. Every account can change its own
at `/account/password`, and the page warns while an account still holds the shared
default.

**Shared mailbox.** `ictmanager` and `icthelpdesk` are both seeded onto
`ictsupport@pbora.go.ke`. A shared address identifies no single account, so those two
sign in by **username**, not by email.

---

## 12. One-command launch with a Cloudflare Tunnel

`LAUNCH_MAINTENANCE.sh` brings the stack up and publishes it at
**https://maintenance.harolditdata.uk** through a Cloudflare Tunnel.

The tunnel dials *out* to Cloudflare, so the server needs **no inbound ports open at
all** — no port forwarding, no nginx, no certbot, and port 5000 can stay firewalled.
Sections 9's reverse proxy is the alternative to this, not a companion to it.

### Once, before the first run

```bash
cloudflared tunnel login        # opens a browser; authorise the harolditdata.uk zone
```

That leaves `~/.cloudflared/cert.pem`, which is what lets the script create tunnels and
DNS records. The script refuses to run without it.

### Every time

```bash
cd /opt/pbora-ict
./LAUNCH_MAINTENANCE.sh
```

It will, in order: check the prerequisites and that `.env` is filled in; build and start
the containers; wait for the app to answer; create the tunnel `pbora-maintenance` (or
reuse it); write `/etc/cloudflared/config.yml`; create the DNS record; install and start
the `cloudflared` systemd service; and check the public URL answers.

Safe to run again — every step detects what it already did. After a `git pull`, running
it again *is* the deploy.

### Options

| Variable | Default | Purpose |
| --- | --- | --- |
| `PUBLIC_HOSTNAME` | `maintenance.harolditdata.uk` | The hostname to publish on |
| `TUNNEL_NAME` | `pbora-maintenance` | Cloudflare tunnel name |
| `APP_PORT` | `5000` | Port the tunnel forwards to |
| `SKIP_TUNNEL` | `0` | `1` brings the stack up and leaves the tunnel alone |
| `OVERWRITE_DNS` | `0` | `1` replaces a DNS record that points somewhere else |
| `APP_READY_TIMEOUT` | `180` | Seconds to wait for the app before giving up |

```bash
SKIP_TUNNEL=1 ./LAUNCH_MAINTENANCE.sh                      # containers only
PUBLIC_HOSTNAME=staging.harolditdata.uk ./LAUNCH_MAINTENANCE.sh
OVERWRITE_DNS=1 ./LAUNCH_MAINTENANCE.sh                    # repoint an existing record
```

### Tunnel housekeeping

```bash
sudo systemctl status cloudflared
sudo journalctl -u cloudflared -f        # tunnel logs
cloudflared tunnel list                  # tunnels on the account
cloudflared tunnel info pbora-maintenance
sudo systemctl restart cloudflared
```

### When the tunnel misbehaves

**`cloudflared` will not start.** Read `sudo journalctl -u cloudflared -n 50`. Usually
the credentials JSON named in `/etc/cloudflared/config.yml` is missing — recreate it by
running the script again.

**502 from Cloudflare.** The tunnel is up but the app is not. `docker compose ps` and
`docker compose logs web`.

**The public URL 404s.** The hostname in the request does not match the `ingress`
hostname in `/etc/cloudflared/config.yml`, so it fell through to the catch-all.

**Live ticket updates stop.** The Socket.IO WebSocket is being closed. The generated
config sets `tcpKeepAlive` and `keepAliveTimeout` for this; check they survived any
hand-editing — the script overwrites that file on each run.

**Credentials file missing for an existing tunnel.** If Cloudflare knows the tunnel but
`~/.cloudflared/<uuid>.json` is gone, the script stops rather than guessing. Delete and
recreate:

```bash
cloudflared tunnel delete pbora-maintenance
./LAUNCH_MAINTENANCE.sh
```

# Deployment Guide (EC2 + Docker)

Live deployment: `http://13.206.247.60:8010`, code at `/opt/replacement-tracker` on the server.

Databases are AWS RDS (not containers): `ez_material_tracker` (app data) and `clappia_integration` (external, read-only).

---

## First-time deployment

1. **Launch EC2** — Ubuntu 22.04/24.04, `t3.small`+. Security group: allow `22` (your IP only) and `8010` inbound; allow `3306` outbound to RDS. Do not open `3306` to the internet.

2. **Install Docker**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER   # log out/in after this
   ```

3. **Clone the repo**
   ```bash
   sudo mkdir -p /opt/replacement-tracker && sudo chown $USER:$USER /opt/replacement-tracker
   git clone https://github.com/Dhawal-Goyal/replacement_tracker_github.git /opt/replacement-tracker
   cd /opt/replacement-tracker
   ```
   (Use a GitHub Personal Access Token as the password when prompted.)

4. **Create `.env`** (gitignored, not in the repo)
   ```bash
   cp .env.example .env
   nano .env
   ```
   Set these:
   ```ini
   SECRET_KEY=<generate below>
   DEBUG=False
   ALLOWED_HOSTS=13.206.247.60
   BIND_HOST=0.0.0.0
   WEB_PORT=8010

   DB_HOST=ecozen-mysql-rds-free-tier.ch9z6zxuoyr5.ap-south-1.rds.amazonaws.com
   DB_PORT=3306
   DB_NAME=ez_material_tracker
   DB_USER=clappia_user
   DB_PASSWORD=<real RDS password>

   CLAPPIA_DB_HOST=ecozen-mysql-rds-free-tier.ch9z6zxuoyr5.ap-south-1.rds.amazonaws.com
   CLAPPIA_DB_PORT=3306
   CLAPPIA_DB_NAME=clappia_integration
   CLAPPIA_DB_USER=clappia_user
   CLAPPIA_DB_PASSWORD=<real RDS password>
   ```
   Generate a `SECRET_KEY`:
   ```bash
   docker run --rm python:3.13-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

5. **Create `config/settings_local.py`** (also gitignored, must exist before build — Django imports it unconditionally)
   ```bash
   cat > config/settings_local.py <<'PYEOF'
   DB_NAME = 'ez_material_tracker'
   DB_USER = 'clappia_user'
   DB_PASSWORD = ''
   DB_HOST = 'localhost'
   DB_PORT = '3306'

   CLAPPIA_DB_NAME = 'clappia_integration'
   CLAPPIA_DB_USER = 'clappia_user'
   CLAPPIA_DB_PASSWORD = ''
   CLAPPIA_DB_HOST = 'localhost'
   CLAPPIA_DB_PORT = '3306'
   PYEOF
   ```

6. **Build and start**
   ```bash
   docker compose up -d --build
   docker compose logs -f web
   ```
   Wait for `Listening at: http://0.0.0.0:8000` in the log, then open `http://13.206.247.60:8010`.

   ⚠️ Do **not** add `--profile local-db` — that starts a local MySQL container production doesn't use.

---

## Pushing a change

```bash
# on your laptop
git add -A && git commit -m "..." && git push origin main
```

```bash
# on the server
cd /opt/replacement-tracker
git pull
docker compose up -d --build
docker compose logs -f web
```

That's it — migrations and `collectstatic` run automatically on start.

Notes:
- `.env` and `config/settings_local.py` are never touched by `git pull`. If you add a new setting, add it to `.env` on the server by hand too.
- Rollback: `git checkout <previous-commit>` then `docker compose up -d --build` (does not undo a migration already applied to RDS).

---

## Useful commands

```bash
docker compose ps                    # status
docker compose logs -f web           # follow logs
docker compose restart web           # restart, no rebuild
docker compose exec web python manage.py shell
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Container loops, exit 255 | `config/settings_local.py` missing | Create it (step 5), rebuild |
| `Timed out waiting for <host>:3306` | RDS unreachable | Check security group allows 3306 from this instance |
| `Unknown database` | Wrong `DB_NAME`/`CLAPPIA_DB_NAME` | Must be `ez_material_tracker` / `clappia_integration` |
| `DisallowedHost` / 400 | IP/domain not in `ALLOWED_HOSTS` | Add it in `.env`, `docker compose up -d` |
| No CSS on page | `collectstatic` failed | Check `docker compose logs web` |
| Port already in use | Another app on 8000 | Already handled via `WEB_PORT=8010` |
| `.env` edit has no effect | `restart` doesn't reread `.env` | Use `docker compose up -d` instead |

---

## Known risks (not yet fixed)

- Passwords stored/checked in plaintext, some accounts share weak passwords.
- No TLS — plain HTTP over a public IP, no reverse proxy in front.
- No off-instance backups of the app database.
- No automated tests (`tracker/tests.py` is empty).

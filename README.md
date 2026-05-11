# Media Monitor

A multi-user web application that monitors a curated list of international media outlets
for mentions of a configurable search term (for example, a university name). Built for
Kobe University; usable by any organisation.

> **Live deployment:** <https://mm.schenz.eu>

![Screenshot placeholder](docs/screenshot.png)

---

## Features

- **Multi-tenant**: every account has its own outlet library, searches, runs, and
  Google API credentials.
- **Per-user encrypted credentials**: Google Custom Search API key + Search Engine ID
  are stored encrypted (Fernet) and never returned in any response.
- **Multilingual search**: one search term per language (English, German, French,
  Spanish, Italian, Portuguese, Russian, Chinese, Korean, Japanese) — Google CSE is
  queried separately per outlet × language.
- **Auto-windowed**: each run automatically looks back to the most recent successful
  run for the same search (default 7 days on first run).
- **Background execution + live status**: runs execute asynchronously; the UI polls
  the run-detail endpoint and renders results as they come in.
- **CSV export**: pick the results you want, optionally roll in selections from prior
  runs, and download a UTF-8 CSV with BOM + RFC 4180 quoting (Excel-friendly).
- **Bulk outlet import / export**: XLSX template with validation report.
- **Webhook trigger**: external systems can start runs via an API key endpoint.
- **Admin console**: create / activate / deactivate / delete users; bootstrap admin
  on first start.
- **Built-in manual**: comprehensive usage guide at `/manual`.

---

## Tech stack

| Layer            | Technology                                              |
|------------------|---------------------------------------------------------|
| Backend          | FastAPI (Python 3.12) + Uvicorn                         |
| ORM / migrations | SQLAlchemy 2.x async + Alembic                          |
| Database         | PostgreSQL 16                                           |
| Auth             | JWT (`python-jose`) + bcrypt (`passlib`)                |
| Background tasks | FastAPI `BackgroundTasks`                               |
| HTTP client      | `httpx` (async, used for Google CSE)                    |
| Frontend         | React 18 + TypeScript + Vite + Tailwind CSS             |
| Encryption       | `cryptography` (Fernet) — for stored Google API keys    |
| Spreadsheets     | `openpyxl`                                              |

---

## Local development

```bash
git clone https://github.com/schoenblum/media-monitor-webapp.git
cd media-monitor-webapp

# Backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in DATABASE_URL, FERNET_KEY, SECRET_KEY, admin email/pass
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (in a second terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

Generate fresh secrets for development:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Run the tests:

```bash
pip install pytest pytest-asyncio httpx aiosqlite
pytest tests/ -v
```

---

## Production deployment (Hetzner / Ubuntu)

The repository was originally provisioned on a Hetzner Cloud VM running Ubuntu 24.04.
The end-to-end setup is documented in the development brief; the abridged version:

1. **Phase 0 — system setup** (one-off, as `root`):
   - Create `deploy` user with sudo privileges scoped to `systemctl restart
     media-monitor` / `systemctl reload nginx`.
   - Install Python 3.12, PostgreSQL 16, Nginx, Certbot, Node.js 20.
   - Configure PostgreSQL with the `media_monitor` database and user.
   - Configure Nginx as a reverse proxy on :80 / :443 to `127.0.0.1:8000`.
   - Obtain a Let's Encrypt certificate via `certbot --nginx`.
   - Install the `media-monitor.service` systemd unit.
2. **Phase 1 — deploy app** (as `deploy`):
   - `git clone …; python3.12 -m venv venv; pip install -r requirements.txt`
   - Write the `.env` file (use `chmod 600`).
   - `cd frontend && npm install && npm run build && cp -r dist/* ../app/static/`
   - `alembic upgrade head`
   - `sudo systemctl start media-monitor`

After the first deployment, future updates are a single command:

```bash
./deploy.sh
```

---

## Environment variables

| Variable                 | Required | Notes |
|--------------------------|----------|-------|
| `SECRET_KEY`             | yes      | JWT signing key |
| `DATABASE_URL`           | yes      | `postgresql+asyncpg://…` |
| `FERNET_KEY`             | yes      | Generated with `Fernet.generate_key()` |
| `BASE_URL`               | yes      | e.g. `https://mm.schenz.eu` |
| `ENVIRONMENT`            | no       | `production` / `development` |
| `BOOTSTRAP_ADMIN_EMAIL`  | yes      | Email of the initial admin account |
| `BOOTSTRAP_ADMIN_PASSWORD` | yes    | Temp password — forced-change on first login |
| `SMTP_HOST` / `_PORT` / `_USER` / `_PASSWORD` / `_FROM` | no | Phase 2; leave empty to log reset URLs to the console |

---

## API documentation

Interactive Swagger UI is available at `/docs` and OpenAPI JSON at `/openapi.json` on
the live server. The REST endpoints sit under `/api/v1/…` and use bearer JWT
authentication for everything except `/auth/login`, `/auth/forgot-password`,
`/auth/reset-password`, and `/webhook/run` (which uses `X-API-Key` instead).

---

## Webhook usage

```bash
curl -X POST https://mm.schenz.eu/api/v1/webhook/run \
     -H "X-API-Key: <your-webhook-key>" \
     -H "Content-Type: application/json" \
     -d '{"search_id": "<uuid-of-your-search>"}'

# → {"run_id": "…", "status": "pending"}
```

Generate the key from **Settings → Webhook API key**. It is shown only once — copy
it immediately. Revoking the key invalidates it server-side; regenerating issues a
new one.

---

## Import template

Download from **Outlets → Template**, fill in, and re-upload. Columns:

| Column         | Required | Notes |
|----------------|----------|-------|
| name           | ✓        | Display name |
| domain         | ✓        | Hostname; `http://` and trailing `/` are stripped |
| category       |          | Free text |
| keyword_langs  |          | Comma-separated language codes (e.g. `en,de`) — defaults to `en` |
| notes          |          | Ignored on import; human reference only |

Two modes:
- **Add** — new rows are inserted, duplicates skipped.
- **Replace all** — wipes your library first, then imports.

The import endpoint returns a validation report `{imported, skipped: [{row, reason}]}`
which is shown directly in the UI.

---

## Contributing

1. Fork the repo and create a feature branch.
2. `pip install -r requirements.txt` + `npm install` inside `frontend/`.
3. Write tests for any backend change (`tests/`).
4. Run `pytest -v` and `cd frontend && npm run build` locally.
5. Open a pull request.

Coding standards: PEP 8 + type hints on the backend; TS strict mode + functional
React components on the frontend; Tailwind utility classes only.

---

## Licence

[MIT](LICENSE)

# Bahraini 28 · bahraini28.com

A lightweight, high-performance **discount tracking portal** for the **Bahraini
28 volunteer organization**. Volunteers browse discounted merchants across
Bahrain, submit physical-store invoice numbers after purchase, and accumulate
shared reward points — while administrators manage users, override
expiries/rewards, and watch purchases arrive in real time.

Monorepo with two independent components:

| Directory    | Stack                                              | Responsibility                         |
| ------------ | -------------------------------------------------- | -------------------------------------- |
| `backend/`   | Python / FastAPI / SQLAlchemy 2 / Pydantic v2      | REST API, security, business rules     |
| `frontend/`  | Vite / React 18 / TypeScript / Tailwind CSS        | Responsive SPA consumed by volunteers  |

---

## Core business rules

- **Strict membership validation**: volunteers log in by **email or CPR**;
  access is blocked once `expiry_date` passes (checked on every request).
- **Single-session enforcement**: each new user login rolls `token_version`,
  invalidating all older tokens. Admins are exempt (multi-tab friendly).
- **Daily usage limit**: at most **3 uses per business per calendar day**
  (independent per business); the counter derives from transactions created
  after the start of the day in `Asia/Bahrain`, so it **auto-resets at
  midnight** with no background job.
- **Duplicate-invoice guard**: the same invoice number can't be submitted
  twice for the same business.
- **First-login profile activation**: new accounts force a name/email/password
  update before first use.
- **Audit trail**: every manual reward adjustment is logged to
  `reward_adjustments`.

---

## Backend

### Tech notes

- `bcrypt` (pyca) for password hashing — `passlib` is unmaintained and was
  deliberately not used.
- `PyJWT` for tokens — `python-jose` has known CVEs and is not used.
- `TZDateTime` (SQLAlchemy `TypeDecorator`) stores UTC and always returns
  timezone-aware datetimes, safe on both SQLite and PostgreSQL.
- Real-time admin notifications use **SSE** through a small in-process
  pub/sub bus (`app/services/notifications.py`). For multi-worker deployment,
  swap the bus for Redis pub/sub — same API surface.

### Run (development)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # or reuse repo venv
pip install -r requirements-dev.txt
cp .env.example .env

# start the API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload --port 8000

# seed demo data (optional)
PYTHONPATH=. python scripts/seed.py
```

Default bootstrapped admin (change in production via `.env`):
`admin` / `admin123`.

### Test

```bash
cd backend
pytest                                   # 44 tests (in-memory SQLite)
```

Re-run the exact same suite against a real PostgreSQL server (used by CI):

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/bahraini28_test pytest
```

Run against PostgreSQL in production by setting
`DATABASE_URL=postgresql+psycopg://user:pass@host/db`.

---

## Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
npm run build      # type-check + production build
```

`vite.config.ts` proxies `/api` and `/uploads` to `http://localhost:8000`, so
local development needs the backend running alongside the dev server. The SPA
defaults to the same-origin API base `/api/v1` (override via `VITE_API_URL`),
so the dev proxy and the production reverse proxy need no extra config.

### Pages

- Public: landing, directory (category/area/search filters), business detail
  (discount %, branches, invoice submission), public transaction history.
- Volunteer: profile + rewards cards + personal history, first-login
  activation modal.
- Admin: dashboard with KPIs + **SSE live purchase feed**, user management
  (CRUD / expiry override / reward adjustment / password reset / activate /
  deactivate), **business management (register / edit / logo upload /
  activate-deactivate partnerships with categories and multi-area
  branches)**, and master
  transaction ledger.

---

## Production deployment (Docker Compose + Caddy)

Everything needed to run on a single VPS (e.g. an Oracle Cloud **Always Free**
Arm VM — Ubuntu 24.04, ≥2 GB RAM — or any Docker host) lives in `deploy/`:

**Stack:** `postgres:17-alpine` (named volume `pgdata`) · FastAPI backend
(`/data/uploads` persistent volume for business logos) · one-shot frontend
builder (compiles `dist/` into a shared volume) · **Caddy** (automatic
renewing Let's Encrypt TLS, serves the SPA, proxies `/api`, `/uploads`,
`/health`).

```bash
git clone https://github.com/SalehAbdulla/bahraini28.git /opt/bahraini28
cd /opt/bahraini28
./deploy/deploy.sh      # one command: tests (if venv) → secrets → build → up → smoke
```

First boot creates the bootstrap admin (`admin` / password from `deploy/.env`).
**Change that password immediately, then set `SEED_DEFAULT_ADMIN=false`** so the
bootstrap account can't be recreated. Optional demo data:

```bash
docker compose -f deploy/docker-compose.yml run --rm backend python scripts/seed.py
```

Operational notes:

- **One uvicorn worker on purpose**: the SSE admin feed uses an in-process
  pub/sub bus. Swap it for Redis pub/sub (same API surface) before scaling.
- **Backups**: `deploy/backup.sh` — daily `pg_dump` (custom format) + uploads
  archive with 14-day retention; cron entry in `deploy/backup-cron.txt`.
  Restore with `deploy/restore.sh <backup.pgdump>`.
- **SQLite → Postgres migration**: `backend/scripts/migrate_sqlite_to_postgres.py`
  (idempotent; re-syncs autoincrement sequences).
- **CI** (`.github/workflows/ci.yml`): backend suite on SQLite **and**
  PostgreSQL 17, plus the frontend type-check + build.

### DNS (Namecheap) → TLS

Create `A` records for `@` and `www` pointing at the VPS public IP, then
Caddy issues and auto-renews certificates automatically — the SPA is served
at `https://bahraini28.com/` and the API at `/api/v1/*`. Optional CAA record:
`0 issue "letsencrypt.org"`. The SSE feed works through the proxy via
`/api/v1/admin/notifications/stream` (admin JWT as `?_token=`).

### E2E tests (Playwright)

Boots the real stack (seeded FastAPI on :8000 + Vite on :5173) against a
throwaway SQLite database and drives it with headless Chromium:

```bash
cd e2e
../.venv/bin/python -m pytest -v    # volunteer journey + admin SSE feed
```

See `docs/project-plan.md` for the original plan and todos.
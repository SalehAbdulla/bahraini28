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
pytest                                   # 44 tests
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
local development needs the backend running alongside the dev server.

### Pages

- Public: landing, directory (category/area/search filters), business detail
  (discount %, branches, invoice submission), public transaction history.
- Volunteer: profile + rewards cards + personal history, first-login
  activation modal.
- Admin: dashboard with KPIs + **SSE live purchase feed**, user management
  (CRUD / expiry override / reward adjustment / password reset / activate /
  deactivate), and master transaction ledger.

---

## Deployment sketch

- Backend: `uvicorn app.main:app` behind a reverse proxy (nginx/Caddy) with
  HTTPS; set a strong `SECRET_KEY`, `CORS_ORIGINS` to the frontend origin,
  and connect PostgreSQL.
- Frontend: `npm run build` → serve the `dist/` directory statically
  (or from the same origin as the API to skip CORS).
- `bahraini28.com` (Namecheap) → DNS A records to the host; TLS via
  Let's Encrypt.
- The SSE notification token passes via `?token=` (needed because browser
  `EventSource` cannot set headers) — keep the admin token short-lived and
  serve behind HTTPS.

See `docs/project-plan.md` for the original plan and todos.
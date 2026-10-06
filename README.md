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
  (independent per business) **and 8 across all partners** (`DAILY_LIMIT_TOTAL`);
  the counters derive from transactions created after the start of the day in
  `Asia/Bahrain`, so they **auto-reset at midnight** with no background job.
- **Invoice-number validation (anti-fraud, Tier 1)**: a submitted invoice must
  match the partner's `invoice_pattern` regex (or a global fallback), and each
  invoice number can be credited **only once per business — by anyone**, so a
  receipt cannot be shared between accounts and junk such as `"!!!"` is
  rejected. Accounts crediting an unusually high number of *distinct* partners
  in one day raise a `fraud_signal` on the admin dashboard.
- **Receipt proof + admin approval (anti-fraud, Tier 2 — shipped)**: a
  submission also carries a **receipt photo/PDF** (`POST /api/v1/transactions`
  is multipart: `business_id`, `invoice_number`, `receipt`). The row is stored
  as `pending` and credits **nothing**; an admin approves it from
  `/admin/reviews` (`POST /api/v1/admin/transactions/{id}/approve`) before the
  reward becomes spendable. Rejecting leaves the balance untouched and records
  why. The same receipt image cannot be reused at one partner (per-partner
  SHA-256 guard), and `pending` submissions still consume the daily caps.
  Set `REQUIRE_RECEIPT_REVIEW=false` to fall back to Tier 1 (instant credit).
  See `docs/ANTI_FRAUD_PLAN.md`.
- **Single-use receipt codes (anti-fraud, Tier 3 — shipped)**: a partner the
  admin flags with `codes_required` only accepts a submission that quotes an
  **unused code the admin issued to that partner** (`B28-XXXX-XXXX`, printed on
  the receipt), so a fabricated number can never be credited. Codes move
  `issued → claimed → redeemed` — claimed while the submission waits in the
  review queue, redeemed on approval, and released back to `issued` if the
  submission is rejected (an honest mistake must not burn the only code on the
  receipt). Admins mint batches and revoke unclaimed codes from
  `/admin/businesses/{id}/codes`. See `docs/ANTI_FRAUD_PLAN.md`.
- **First-login profile activation**: new accounts force a name/email/password
  update before first use.
- **Audit trail**: every manual reward adjustment **and every invoice approval**
  is logged to `reward_adjustments` (approvals as `invoice approval #<id>`).

---

## Run locally (hot reload)

`run.sh` starts both servers, each watching its own source tree:

```bash
./run.sh            # API on :8000 + SPA on :5173
./run.sh --seed     # ...plus demo businesses, a volunteer login and a code-required partner
./run.sh --partners # ...plus the 28 elite-card partners, their logos and discounts
./run.sh --areas    # ...plus the real Bahrain area list (idempotent)
./run.sh --help     # all flags: --backend-only, --frontend-only, --web-port
```

It reuses the repo `.venv` (creating it and installing `requirements-dev.txt` /
`npm ci` only when needed), creates `backend/.env` from the example on first
run, and stops both servers on Ctrl-C. `WEB_PORT` overrides the SPA port; leave
`API_PORT` at 8000 unless you also change the proxy target in
`frontend/vite.config.ts`.

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
- Uploaded files (business logos + invoice receipts) share one helper
  (`app/services/uploads.py`) and one cap, `MAX_UPLOAD_SIZE_MB`. Receipt photos
  are downscaled in the browser first (`frontend/src/lib/receipt.ts`), so the cap
  is a backstop — a phone JPEG is routinely 3-5 MB, a legible receipt a few
  hundred KB — and the input requests the rear camera on mobile.
- **Uploads are only partly public.** `/uploads/<file>` serves a file *only when
  a partner references it as their logo* (`app/api/routes/uploads.py`); there is
  no blanket static mount. Invoice receipts share the same directory on disk but
  are served to admins only, from `/api/v1/admin/receipts/<file>`, so a leaked
  receipt URL is inert.

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

# import the real Bahrain area list (optional, idempotent)
PYTHONPATH=. python scripts/seed_areas.py

# seed the 28 elite-card partners, logos included (optional, idempotent)
PYTHONPATH=. python scripts/seed_partners.py
```

Default bootstrapped admin (change in production via `.env`):
`admin` / `admin123`.

### Test

```bash
cd backend
pytest                                   # 69 tests (in-memory SQLite)
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
  (discount %, branches, invoice **+ receipt** submission), public transaction
  history.
- Volunteer: profile + rewards cards split into **approved (spendable)** and
  **awaiting review**, personal history with per-row `pending`/`approved`/
  `rejected` status, first-login activation modal.
- Admin: dashboard with KPIs + **SSE live purchase feed** +
  **receipt review queue (`/admin/reviews`: receipt thumbnail, approve/reject
  with an optional reason)**, user management
  (CRUD / expiry override / reward adjustment / password reset / activate /
  deactivate), **business management (register / edit / logo upload / a benefit
  label for a deal that is not a flat percentage / activate-deactivate
  partnerships with categories and multi-area branches)**,
  **single-use receipt-code batches (`/admin/businesses/{id}/codes`:
  mint / filter / revoke)**, **areas & categories management**, and master
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
bootstrap account can't be recreated. Use the dashboard's *Change password*
button, or — before the first login, and for recovery — the CLI:

```bash
docker compose -f deploy/docker-compose.yml run --rm backend \
    python scripts/set_admin_password.py --username admin
```

Optional seed data:

```bash
# demo businesses, a volunteer login and a code-required partner
docker compose -f deploy/docker-compose.yml run --rm backend python scripts/seed.py

# the 28 elite-card partners with their logos (idempotent; re-running never
# touches a row an admin has edited)
docker compose -f deploy/docker-compose.yml run --rm backend python scripts/seed_partners.py
```

Operational notes:

- **Admin credentials**: the dashboard's *Change password* button posts to
  `POST /api/v1/admin/me/password` (the current password is re-verified).
  `scripts/set_admin_password.py` covers the bootstrap rotation and
  lost-password recovery, when no admin session exists yet. Admins are exempt
  from single-session invalidation, so rotating does not sign other tabs out.
- **One uvicorn worker on purpose**: the SSE admin feed uses an in-process
  pub/sub bus. Swap it for Redis pub/sub (same API surface) before scaling.
- **Backups**: `deploy/backup.sh` — daily `pg_dump` (custom format) + uploads
  archive with 14-day retention; cron entry in `deploy/backup-cron.txt`.
  `deploy/offsite-backup.sh` then copies both artifacts **off this host** with
  `rclone` (config: `deploy/offsite.env`) — without it, every backup lives on the
  same disk as the data it protects. A ready-made **Oracle Object Storage** remote
  (free tier; instance-principal, user-key and S3-compatible flavours) is in
  `deploy/rclone-oci.conf.example`. Restore a *pair* from the same run:

  ```bash
  sudo deploy/restore.sh bahraini28-<stamp>.pgdump uploads-<stamp>.tar.gz
  ```

  The uploads archive is what puts the receipts and logos back; restoring the
  dump alone leaves every `receipt_path` pointing at a file that is gone.
- **SQLite → Postgres migration**: `backend/scripts/migrate_sqlite_to_postgres.py`
  (idempotent; re-syncs autoincrement sequences).
- **CI** (`.github/workflows/ci.yml`): backend suite on SQLite **and**
  PostgreSQL 17, the frontend type-check + build, and the **Playwright e2e
  suite** (volunteer journey, admin SSE feed and the balanced-gutter layout
  guard on every touched page).

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
.venv/bin/python -m pip install -r e2e/requirements.txt   # backend dev deps + Playwright
.venv/bin/playwright install --with-deps chromium         # one-off browser download
cd e2e
../.venv/bin/python -m pytest -v                          # journey + layout guard
```

`e2e/requirements.txt` also pulls in `backend/requirements-dev.txt`, because the
suite shells out to `uvicorn` and `backend/scripts/seed.py` with the same
interpreter that runs pytest.

This suite runs in CI as the `E2E (Playwright)` job, so a broken journey or a
layout regression fails the build rather than only showing up locally.

See `docs/project-plan.md` for the original plan and todos.
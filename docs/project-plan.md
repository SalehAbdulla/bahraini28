# Bahraini 28 — Discount Tracking Portal

**Project Name & Vision**: Bahraini 28 (Discount Tracking Portal for the Bahraini 28 Volunteer Organization). A lightweight, high-performance web platform designed to digitize and track exclusive member discounts at physical merchant locations.

---

## Target Audience & Actors

- **Admin**: Complete system control, user management, manual reward adjustments, expiry date overrides, global purchase tracking, and real-time transaction notifications.
- **Users (Volunteers)**: Authenticated members who browse discounted businesses, submit physical store invoices to increment reward metrics, and monitor personal usage history.
- **Businesses**: Physical merchant partners offering tiered discounts across single or multiple geographic areas. Businesses operate offline via physical verification and do not require digital user accounts or login portals.

---

## Core Value Proposition

Seamlessly bridges physical retail interactions with digital accountability, ensuring strict membership validation via expiry checks, single-session security, and real-time administrative oversight.

---

## Technical Scope & Architecture

- **Backend Framework**: Python with FastAPI (high performance, auto-documentation, minimal boilerplate).
- **Database & ORM**: SQLite/PostgreSQL via SQLAlchemy (leveraging automated table creation and clean relational mapping for Users, Businesses, Areas, and Transactions).
- **Validation & Security**: Pydantic v2 (strict payload validation), Passlib with Bcrypt (secure credential hashing), and JWT-based session tokens with single-device enforcement.
- **Frontend & Asset Management**: Server-rendered templates or a clean component layout styled with Tailwind CSS, supporting responsive mobile-first views for fast physical store invoice submissions.

---

## System Workflow & Functional Matrix

| Module | Core Features & Business Rules |
|--------|-------------------------------|
| **Authentication & Security** | • Multi-identifier login (Email or CPR for Users; Username/Password for Admins).<br>• Expiry validation blocks access for lapsed memberships.<br>• First-login modal forces temporary password updates (Name, Email, New Password).<br>• Single-session enforcement invalidates prior tokens on new logins (Admins exempt). |
| **Admin Control Center** | • Full CRUD for Users (modify details, reset passwords, change expiry dates, manually adjust reward counters).<br>• Paginated user audit trail tracking transaction history, age, timestamps, and favorite merchant categories.<br>• Real-time purchase alert notification feed and master transaction ledger showing invoice numbers. |
| **Business Directory & Categories** | • Public catalog of participating merchants organized by structured categories and multi-branch geographic areas.<br>• Detail view displaying discount percentages, logos, active areas, invoice input forms, and paginated public transaction histories. |
| **User Portal & Rewards** | • Profile view showing personal credentials, membership status, and a dynamic rewards metrics card.<br>• Invoice submission engine: users input physical receipt invoice numbers post-purchase to automatically increment reward counters.<br>• **Daily usage limit**: max 3 successful uses per business per calendar day (independent per business), auto-reset at midnight. |

---

## Project Implementation Todo List

### Phase 1: Project Setup & Database Models — ✅ done
- [x] Initialize FastAPI project structure with virtual environment and dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`). Note: **bcrypt** and **PyJWT** were used instead of `passlib[bcrypt]`/`python-jose` (both unmaintained / have CVEs).
- [x] Configure SQLAlchemy database engine and session management (SQLite for dev, PostgreSQL for prod; `pool_pre_ping`).
- [x] Build database models: `Admin`, `User` (CPR, email, password_hash, expiry_date, first_login flag, token_version), `Business` (name, CR, logo_path, discount_percentage, expiry_date), `BusinessArea` (relationship table for multi-branch locations), `Transaction` (user_id, business_id, invoice_number, timestamp, reward_increment), plus `Category`, `Area`, `RewardAdjustment` (audit log).

### Phase 2: Authentication, Security & Middleware — ✅ done
- [x] Implement secure password hashing utility using `bcrypt` (pyca).
- [x] Create JWT token generation and validation dependencies with single-session tracking (`token_version` check).
- [x] Build login endpoints for Users (supporting CPR or Email lookup, expiry date validation, and temporary password detection) and Admins.
- [x] Implement profile-activation middleware/endpoint to force first-time users to update their name, email, and password.

### Phase 3: Admin Dashboard & Management APIs — ✅ done
- [x] Develop Admin user-management endpoints (Add, Modify, Deactivate users, override expiry dates, and manual reward adjustments).
- [x] Build detailed user analytics query (transaction history, aggregate metrics, most-frequented business).
- [x] Implement master transaction log endpoint with pagination and real-time notification hooks (SSE admin feed).

### Phase 4: Business Directory & User Interface — ✅ done
- [x] Create public landing page, login page (with "Volunteer Members Only" notice), and categorized business directory home page.
- [x] Build individual business component view displaying logo, discount %, branch areas, and invoice submission form.
- [x] Develop user profile view featuring member details, reward tracking cards, and transaction history.

### Phase 5: Frontend Polish & Testing — ✅ done
- [x] Style all views using Tailwind CSS for clean, minimalist, mobile-friendly UX.
- [x] Write integration tests for authentication flows, expiry checks, single-session token invalidation, and invoice reward increments (44 backend tests, SQLite + PostgreSQL via `TEST_DATABASE_URL`).
- [x] Playwright E2E suite under `e2e/`: volunteer journey (login → first-login modal → directory → invoice → profile reward) and admin dashboard SSE live feed.

### Phase 6: Anti-fraud hardening — ✅ done
- [x] **Tier 1** (see `docs/ANTI_FRAUD_PLAN.md`): per-partner `invoice_pattern`
      regex + global fallback, global duplicate guard
      `UNIQUE(business_id, invoice_number)`, per-business and total daily caps,
      `fraud_signal` SSE alert. Reconciles existing databases in
      `app/db/bootstrap.py`.
- [x] **Tier 2** (receipt proof + admin approval): multipart submission with a
      receipt (`business_id`, `invoice_number`, `receipt`), per-partner receipt
      SHA-256 de-duplication, `pending → approved | rejected` lifecycle
      (`transactions.status` / `receipt_path` / `receipt_sha256` /
      `reviewed_by` / `reviewed_at` / `rejection_reason`), the admin review API
      (`GET /api/v1/admin/transactions/review`,
      `POST .../{id}/approve`, `POST .../{id}/reject`) and queue UI
      (`/admin/reviews`), `RewardAdjustment` audit row on every approval, the
      `invoice_reviewed` SSE event, the `/admin/reviews` layout guard in
      `e2e/test_layout.py`, and the `REQUIRE_RECEIPT_REVIEW` rollout switch.
      `app/db/bootstrap.py::_ensure_review_columns` migrates existing databases
      and backfills legacy rows to `approved` (no rewards lost).
- [x] **Tier 3** (merchant single-use codes): per-partner
      `businesses.codes_required` opt-in, globally-unique `B28-XXXX-XXXX` codes
      in a new `invoice_codes` table (`app/services/invoice_codes.py`), the
      admin issue/list/stats/revoke API
      (`POST|GET /api/v1/admin/businesses/{id}/codes`,
      `GET .../codes/stats`, `DELETE /api/v1/admin/codes/{id}`) and page
      (`/admin/businesses/{id}/codes`), `transactions.code_id`, and the
      `issued → claimed → redeemed` lifecycle (released back to `issued` on
      rejection). `app/db/bootstrap.py::_ensure_code_columns` migrates existing
      databases. The `/admin/businesses/{id}/codes` page is covered by the
      `e2e/test_layout.py` gutter guard.

---

## Domain

**bahraini28.com** — purchased via Namecheap.

---

## Additional System Update (Daily Usage Limit)

**Rules:**

- **Maximum limit per business:** Each volunteer is entitled to use the discount at any single business a maximum of **3 times per day**.
- **Flexibility across different businesses:** Volunteers can enjoy discounts at other businesses on the same day without any issues, as the 3-time limit is independent for each business.
- **Automatic renewal:** Once the date changes, midnight passes, and a new day begins, the 3 attempts for each business are **automatically reset and renewed** so the volunteer can use them again.

---

## Todo List Update for Programming This Feature

**Phase 1 & 2 (Database & Registration):**
- [x] Add a condition in the transactions table to verify the number of times a business has been used, ensuring that it only counts purchases made **within the current calendar day** (derived from `Asia/Bahrain` day start, no background job).

**Phase 3 & 4 (Business Page & Verification):**
- [x] Program the verification system when a volunteer enters an invoice number: if they have reached 3 successful attempts at the same business during the same day, display a notice stating that the daily limit for this business has been exhausted, while still allowing purchases from other businesses (`DAILY_LIMIT_PER_BUSINESS` configurable).
- [x] Ensure the system automatically resets the counter at the start of every new day.

---

## Additional System Update (Areas & Categories Management)

The directory's area filter and merchant categories are data-driven rather than
hard-coded, and administrators manage them from the control center:

- [x] Bundle the organization's official Bahrain area list
  (`backend/data/bahrain_areas.csv` — 164 distinct areas across 4
  governorates, derived from the provided address dataset) and import it
  idempotently via `backend/scripts/seed_areas.py`.
- [x] Admin API + UI (`/admin/catalog`) to add, rename, activate/deactivate and
  delete **areas**, and to add, rename and delete **categories** (slug
  auto-generated from the name).
- [x] Deletion guards: deleting an area still linked to a business branch, or a
  category still assigned to a business, returns `409` instead of cascading.

---

## Brand Identity & Assets

The look follows the organization's official deck (`docs/Bahraini 28 3.pdf`
plus `docs/Fonts.zip`). Those originals are ~37 MB and **git-ignored**, so
everything the app actually serves is derived once from the deck and committed
under `frontend/public/` — no build step depends on the originals.

- **Palette** sampled straight from the deck: brand green **`#6db193`**
  (identical on pages 3-5 and 8-9), paper cream `#fff8e4`, ink `#1a1a1a`,
  brush grey `#878787`. Wired into `frontend/tailwind.config.js`, which also
  defines `brand-700` (`#447f66`) because `#6db193` on white is only ~2.3:1 —
  solid buttons and links use `brand-700` to stay WCAG AA.
- **Script face**: `HOOKER.otf` from `Fonts.zip` is self-hosted at
  `frontend/public/brand/fonts/HOOKER.otf` as `font-script`, used only as a
  display accent ("Hello Bahrainies!", "Soon!", step numerals, the footer
  wordmark). Body copy stays on the system sans stack — no webfont download.
- **Textures**: `texture-cream.jpg` (page 4 band), `texture-mint.jpg` (page 7),
  `texture-ink.jpg` (page 5) — logo-free watercolour bands used as section
  washes via the `bg-texture-*` utilities.
- **Logo & badge**: `brand/logo-sm.png` (431×240) is the one the UI actually
  loads — it is the header mark and both landing-page marks; `brand/logo.png`
  (862×480) is kept as the high-resolution master (the deck it is cut from is
  git-ignored, so the repo must hold the best copy). `brand/badge.png` (768 px,
  hero) and `brand/badge-sm.png` (160 px, 44 px footer slot) are the same cream
  disc sized per use, so no page ships the hero file for a thumbnail.
- **Icons & previews**: `favicon.png`, `favicon.ico`, `apple-touch-icon.png`
  and `og-image.jpg` (1200×630), all referenced from `frontend/index.html`,
  which also preloads the script face and sets `theme-color`.

### Regeneration recipe

Needs `ghostscript` (page raster) and ImageMagick v7 (`magick`). With
`W=/tmp/br` and `OUT=frontend/public/brand`:

```bash
# --- logo plate (page 3) and the watercolour bands (pages 4, 5, 7) ---
for p in 3 4 5 6 7 8 9; do
  gs -q -dNOSAFER -dNOPAUSE -dBATCH -sDEVICE=pngalpha -r150 \
     -dFirstPage=$p -dLastPage=$p -sOutputFile=$W/p$p.png "docs/Bahraini 28 3.pdf"
done

# --- logo (trim the transparent plate) ---
magick $W/p3.png -trim +repage $W/logo_trim.png
magick $W/logo_trim.png -resize x480 -define png:compression-level=9 -strip $OUT/logo.png
magick $W/logo_trim.png -resize x240 -define png:compression-level=9 -strip $OUT/logo-sm.png

# --- badge: cream disc + grey ring + centred logo, then per-use sizes ---
magick -size 1200x1200 xc:none -fill '#fff6dc' -stroke '#a7a6a6' -strokewidth 18 \
       -draw 'circle 600,600 600,14' $W/badge_base.png
magick $W/badge_base.png \( $W/logo_trim.png -resize x430 \) \
       -gravity center -composite -depth 8 -strip $W/badge_master.png
magick $W/badge_master.png -resize 768x768 -strip $OUT/badge.png
magick $W/badge_master.png -resize 160x160 -colors 96 -strip $OUT/badge-sm.png

# --- textures: logo-free bands of the watercolour pages ---
# -alpha remove is REQUIRED: these renders are RGBA and page 7's transparent
# right margin composites to a solid black bar in JPEG if it is not flattened.
magick $W/p4.png -crop 2344x1523+0+3146 +repage -background '#fff8e4' -alpha remove -alpha off \
       -resize 1600x -quality 82 -strip $OUT/texture-cream.jpg
magick $W/p7.png -crop 2330x1370+0+2943 +repage -background '#fff8e4' -alpha remove -alpha off \
       -resize 1600x -quality 82 -strip $OUT/texture-mint.jpg
magick $W/p5.png -crop 2344x1522+0+101  +repage -background '#fff8e4' -alpha remove -alpha off \
       -resize 1600x -quality 82 -strip $OUT/texture-ink.jpg

# --- icons + social card ---
magick $OUT/badge.png -resize 64x64   -strip frontend/public/favicon.png
magick $OUT/badge.png -resize 180x180 -strip frontend/public/apple-touch-icon.png
magick $OUT/badge.png -define icon:auto-resize=16,32,48 -strip frontend/public/favicon.ico
magick $OUT/texture-cream.jpg -resize 1200x -gravity center -crop 1200x630+0+0 +repage \
       \( $W/logo_trim.png -resize x300 \) -gravity center -composite \
       -quality 88 -strip frontend/public/og-image.jpg

# --- script face (unzip Fonts.zip first) ---
cp HOOKER.otf $OUT/fonts/HOOKER.otf
```

Two traps worth remembering when adjusting this: always keep the `-alpha remove`
step on the textures, and never write a 16-bit render straight to PNG for the
web — quantising *without* forcing `-depth 8` leaves a low-colour file that
still costs six bytes a pixel. Sanity checks after a rebuild:

```bash
# no near-black pixels in the mint wash (a low value means the flatten was skipped)
magick $OUT/texture-mint.jpg -format '%[fx:minima*255]\n' info:   # expect >180
magick $OUT/badge.png   -format '%[channels]\n' info:              # expect "srgba 4.0"
```

---

## Production Deployment

Target: **Oracle Cloud Always Free** (Ampere A1 ARM, Ubuntu 24.04, ≥2 GB RAM)
or any Docker host. Full artifacts in `deploy/`, run guide in `README.md`:

- `deploy/docker-compose.yml` — PostgreSQL 17 (named volume `pgdata`),
  FastAPI backend (uploads volume, single uvicorn worker for the in-process
  SSE bus), one-shot frontend builder, **Caddy** (auto-renewing TLS, serves
  SPA, proxies `/api`, `/uploads`, `/health`).
- `deploy/deploy.sh` — one-command deploy + smoke path; `backup.sh` /
  `restore.sh` — daily `pg_dump` + uploads archive with 14-day retention.
- `deploy/.env.production.example` — production env template (DB credentials,
  secret keys, CORS for https://bahraini28.com). `backend/.env.example` — local.
- CI (`.github/workflows/ci.yml`) runs the backend suite on SQLite **and**
  PostgreSQL 17, the frontend build, and the Playwright e2e suite
  (`e2e/requirements.txt` declares its deps).
- `backend/scripts/migrate_sqlite_to_postgres.py` — idempotent data migration.
- DNS (Namecheap): `A @` and `A www` → VPS IP; CAA `0 issue "letsencrypt.org"`.

**Remaining operational checklist (after the VPS + DNS are live):**
- [ ] Change the bootstrap admin password (`scripts/set_admin_password.py`, or the
      dashboard's *Change password*) and set `SEED_DEFAULT_ADMIN=false`.
- [ ] Verify `https://bahraini28.com` SPA, `/api/v1` health, and the SSE feed.
- [ ] Install the daily backup cron entry (`deploy/backup-cron.txt`) and test one restore.

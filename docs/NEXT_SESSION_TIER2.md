# Next session — Tier 2: receipt proof + admin approval

**Status:** ready to execute. Tier 1 is shipped (see `docs/ANTI_FRAUD_PLAN.md`).

## Why this is the next thing

Tier 1 stopped the *easy* abuse (junk invoice numbers, receipt reuse, directory
farming) but it is still **trust-based** — a volunteer can type a plausible,
unused invoice number and be credited instantly. Tier 2 makes a purchase
**provable**: the volunteer attaches a receipt photo and an admin approves it
before any reward is credited.

## Current behaviour (the thing being changed)

`POST /api/v1/transactions` → `app/services/transactions.py::submit_invoice`
immediately does `user.reward_points += 1`. Nothing is reviewed.

```
BusinessDetail.tsx  --POST-->  /transactions  -->  +1 reward instantly
```

## Target behaviour

```
BusinessDetail.tsx --multipart--> /transactions -> Transaction(status=pending, receipt_path=...)
                                                        |
                                     admin review queue (SSE + dashboard)
                                                        |
                        POST /admin/transactions/{id}/approve  -> +1 reward + audit row
                        POST /admin/transactions/{id}/reject   -> no reward
```

---

## Step 1 — Model: add the review lifecycle

`backend/app/models/transaction.py`

Add:

```python
status: Mapped[str] = mapped_column(String(16), default="pending", index=True, nullable=False)
receipt_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
receipt_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)
reviewed_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Use `status` values `"pending" | "approved" | "rejected"` (plain string +
index; the project uses no Enum type elsewhere).

**Do not reuse `reward_increment`** — keep it as the amount credited on
approval so reporting stays simple.

## Step 2 — Migration (existing databases)

`backend/app/db/bootstrap.py` already reconciles the Tier 1 changes. Add a
third step, `_ensure_review_columns`, in the same style:

- add the six columns above via `ALTER TABLE transactions ADD COLUMN ...`,
  guarded by `inspect(engine).get_columns("transactions")`;
- **backfill** so existing rows are not retro-actively un-credited:
  `UPDATE transactions SET status='approved' WHERE status IS NULL` (and set
  `reviewed_at = created_at` so ledger order is preserved);
- register the step in the `reconcile_schema` tuple.

Add a test that runs `reconcile_schema` against a hand-built pre-Tier-2 schema
and asserts the columns exist, the backfill ran, and a second call is a no-op.
Extend `backend/tests/test_bootstrap_migration.py` (it already builds the legacy
schema for the Tier 1 migration) with a `status`/backfill case.

## Step 3 — Submission becomes multipart with a receipt

`backend/app/api/routes/transactions.py`

Change the handler to accept `UploadFile`:

```python
@router.post("", response_model=TransactionCreatedOut, status_code=201)
async def submit_invoice(
    business_id: int = Form(...),
    invoice_number: str = Form(..., min_length=3, max_length=64),
    receipt: UploadFile = File(...),
    user: CurrentUser = ...,
    db: DbSession = ...,
    settings: AppSettings = ...,
):
```

Reuse the **existing** upload machinery from
`routes/admin.py::upload_business_logo` (do not invent a second one):

- a content-type allowlist like `_ALLOWED_LOGO_TYPES` → new
  `_ALLOWED_RECEIPT_TYPES` (PNG/JPEG/WebP + `application/pdf`);
- enforce `MAX_UPLOAD_SIZE_MB` via the existing `FileTooLargeError` /
  `UnsupportedFileTypeError`;
- write to `settings.UPLOAD_DIR`, filename `r{business_id}-{uuid4}{ext}`,
  served at `/uploads/{filename}`;
- compute `receipt_sha256 = hashlib.sha256(payload).hexdigest()`.

Then delegate to the service. Keep the Tier 1 gates exactly as they are
(format → global duplicate → per-business cap → total cap).

## Step 4 — Service: create `pending`, do not credit

`backend/app/services/transactions.py`

- `submit_invoice(...)` gains `receipt_path` / `receipt_sha256` params and
  creates the row with `status="pending"`.
- **Remove** `user.reward_points += ...` from `submit_invoice`.
- Reject a duplicate receipt image for the same partner (same
  `receipt_sha256` already seen at that `business_id`) with the existing 409
  `duplicate_invoice` semantics and a new message.
- Leave the daily counters **unchanged** — they must still count `pending` +
  `approved`, otherwise queueing bypasses the caps.
- New functions:
  - `approve_transaction(db, *, admin, transaction)` → `status="approved"`,
    set `reviewed_by` / `reviewed_at`, `user.reward_points += reward_increment`,
    and insert a `RewardAdjustment(delta=+1, reason=f"invoice approval #{id}",
    admin_id=admin.id, user_id=...)` audit row. Raise on non-pending rows.
  - `reject_transaction(db, *, admin, transaction, reason)` → `status="rejected"`,
    store `rejection_reason`; never touch `reward_points`.
  - `paginate_for_review(db, *, status="pending", page, page_size)`.

## Step 5 — Admin endpoints

`backend/app/api/routes/admin.py`

```python
@router.get("/transactions/review", response_model=Page[TransactionReviewOut])
@router.post("/transactions/{transaction_id}/approve", response_model=TransactionReviewOut)
@router.post("/transactions/{transaction_id}/reject", response_model=TransactionReviewOut)
```

`TransactionReviewOut` (new, in `schemas/transaction.py`) extends
`TransactionOut` with `user_id`, `user_name`, `status`, `receipt_url`,
`reviewed_at`, `rejection_reason`.

Reuse `bus.publish` to emit `"invoice_reviewed"` so other admin tabs refresh.

## Step 6 — Frontend

- **`src/types/index.ts`** — add `status`, `receipt_url`, `reviewed_at`,
  `rejection_reason` to the transaction types; add `TransactionReviewOut`.
- **`src/api/client.ts`** — add a multipart submit (extend `apiUpload` to take
  extra form fields, or add `apiSubmitInvoice`).
- **`src/pages/BusinessDetail.tsx`** — add a required
  `<input type="file" accept="image/*,application/pdf">`; on success show
  *"Submitted — your reward is credited once the receipt is reviewed."*
  Do **not** show `+1 reward` any more.
- **`src/pages/Profile.tsx`** — split the balance into **Approved** (spendable)
  and **Pending**; show `status` per history row.
- **`src/pages/AdminDashboard.tsx`** (or a new `AdminReviews.tsx`) — review
  queue: receipt thumbnail (click → full image), invoice number, volunteer,
  partner, submitted time, Approve / Reject + optional reason.

Respect the design constraints already in force: **sharp corners, editorial
serif headings, ink/cream palette, no new colours or fonts.**

## Step 7 — Config & rollout

`backend/app/core/config.py`

```python
REQUIRE_RECEIPT_REVIEW: bool = True   # False => Tier 1 behaviour (instant credit)
```

When `False`: receipt optional and credit immediately, so the Tier 1 tests and
a pre-onboarding deployment keep working. When `True`: receipt required,
`pending` until approved.

## Step 8 — Tests

New `backend/tests/test_receipt_review.py`:

1. submit without a receipt → 422/400 (when `REQUIRE_RECEIPT_REVIEW=True`)
2. submit with a receipt → 201, `status == "pending"`, `reward_points`
   unchanged
3. approve → `reward_points +1`, `status == "approved"`, `reviewed_by` set, a
   `RewardAdjustment` row exists
4. reject → `reward_points` unchanged, `rejection_reason` stored
5. approving a non-pending row → 409
6. duplicate receipt image at the same partner → 409
7. daily caps still count `pending` rows
8. `reconcile_schema` backfills legacy rows to `approved`
9. the Tier 1 suite still passes with `REQUIRE_RECEIPT_REVIEW=False`

Run: `cd backend && PYTHONPATH=. ../.venv/bin/python -m pytest -q`
(currently **79 passed** — it must stay green).

## Step 9 — Docs

- Update `docs/ANTI_FRAUD_PLAN.md`: mark Tier 2 shipped with the real
  column/endpoint names.
- Update `README.md` business rules: rewards are credited **after review**.
- Update the `docs/project-plan.md` phase checklist.

---

## Acceptance criteria

- [ ] No code path credits `reward_points` except `approve_transaction` and an
      admin manual adjustment.
- [ ] A submission with no readable receipt can never reach `approved`.
- [ ] Every approval is traceable to an admin id + timestamp + audit row.
- [ ] Legacy transactions are backfilled to `approved` (no rewards lost).
- [ ] Sharp corners, editorial serif headings, and balanced gutters
      (`scrollWidth === innerWidth`) are preserved on every touched page.
- [ ] Full backend suite green; frontend `npm run build` green.

## Gotchas to remember

- **Daily caps must count `pending` too**, or queueing bypasses them.
- **`submit_invoice` is currently called only by `routes/transactions.py`** —
  grep for other callers/tests before changing its signature.
- **`test_daily_limit.py` / `test_transactions.py` assert an instant balance.**
  They need the `REQUIRE_RECEIPT_REVIEW=False` fixture path or updated
  expectations.
- **The e2e journey** (`e2e/test_journey.py`) submits an invoice and asserts the
  reward appears immediately; update it to the approval flow.
- **Do not use `!important`**, `100vw`, or negative margins in the new UI.
- Reuse the existing upload pipeline; do not add a second storage mechanism.

## Verification commands

```bash
# backend suite
cd backend && PYTHONPATH=. ../.venv/bin/python -m pytest -q

# pre-Tier-2 schema migration check (already covered by
# backend/tests/test_bootstrap_migration.py — add a status/backfill case there)
cd backend && PYTHONPATH=. ../.venv/bin/python -m pytest tests/test_bootstrap_migration.py -q

# frontend build + type-check
cd frontend && npm run build
```

## Open product questions (decide before/while building)

1. Who reviews — every admin, or a designated reviewer role?
2. SLA/reminder if a submission sits pending for N days?
3. Should a rejection allow one re-submission with a better photo?
4. Do we tell the volunteer *why* a receipt was rejected?
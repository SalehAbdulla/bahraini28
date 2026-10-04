# Anti-fraud plan for invoice-submitted rewards

## The problem

Rewards are credited when a volunteer types an invoice number from a physical
receipt (`POST /api/v1/transactions`). Nothing in the original design proved a
purchase happened:

- Any string of 3–64 characters was accepted (`"1"`, `"AAA"`, …).
- Uniqueness was scoped to `(user_id, business_id, invoice_number)`, so the
  same receipt could be reused by a different account.
- The only ceiling was 3 uses **per business**, which is meaningless against a
  directory of dozens of partners.

A single account could therefore fabricate ~`3 x N` rewards per day, every day.

## Tier 1 — shipped (hardening, no partner integration)

| Control | Where | Effect |
| --- | --- | --- |
| `invoice_pattern` per partner (regex, full match) + global fallback | `Business.invoice_pattern`, `services/transactions.validate_invoice_format` | Rejects implausible invoices (`"!!!"`, blank-ish strings, wrong prefix). |
| Global duplicate guard `UNIQUE(business_id, invoice_number)` | `models/transaction.py`, `services/transactions.submit_invoice` | An invoice is credited once per partner **by anyone** — receipt sharing dies. |
| Total daily cap `DAILY_LIMIT_TOTAL` | `core/config.py`, `services/transactions.count_uses_today_total` | Stops directory farming; also exposed to the client as `remaining_today_total`. |
| Fraud signal | `routes/transactions.py` → SSE `fraud_signal` | Dashboard alert when one account credits ≥ `FRAUD_DISTINCT_BUSINESSES_PER_DAY` distinct partners in a day. |
| Canonical invoice form | `normalize_invoice_number` | Trim + upper-case, so `inv-77` and `INV-77` collide as intended. |

`app/db/bootstrap.py` reconciles an **existing** database on startup (adds the
column, widens the uniqueness rule) since the project ships no migration tool.

**Honest limit:** Tier 1 makes farming impractical but is still trust-based —
it cannot prove the receipt exists.

## Tier 2 — shipped (receipt proof + admin approval)

Goal achieved: a reward is now *proven*, not asserted. A volunteer attaches a
photo/PDF of the receipt, and an admin approves it before any reward is
credited.

| Control | Where | Effect |
| --- | --- | --- |
| Receipt evidence on submission | `routes/transactions.py` (multipart: `business_id`, `invoice_number`, `receipt`) | The receipt file is written through the **single shared upload helper** `services/uploads.py::store_upload` (same `UPLOAD_DIR` / `MAX_UPLOAD_SIZE_MB` / `FileTooLargeError` / `UnsupportedFileTypeError` as the logo upload); PNG/JPEG/WebP/PDF only. |
| Receipt hash de-duplication | `Transaction.receipt_sha256` + `services/transactions.submit_invoice` | The same image cannot back two invoices at one partner (409 `duplicate_invoice`). |
| Review lifecycle | `Transaction.status` (`pending` / `approved` / `rejected`), `receipt_path`, `receipt_sha256`, `reviewed_by`, `reviewed_at`, `rejection_reason` | A submission lands `pending` and **credits nothing**. |
| Approval is the only credit path | `services/transactions.approve_transaction` | `+reward_increment` on `User.reward_points` **and** a `RewardAdjustment` audit row (`delta=+1`, `reason="invoice approval #<id>"`, `admin_id`). Re-approving a decided row → 409 `transaction_not_pending`. |
| Rejection touches nothing | `services/transactions.reject_transaction` | Stores `rejection_reason`; `reward_points` is never modified. |
| Admin review API | `GET /api/v1/admin/transactions/review`, `POST /api/v1/admin/transactions/{id}/approve`, `POST /api/v1/admin/transactions/{id}/reject` | Queue is oldest-first; approve/reject return `TransactionReviewOut` (volunteer, receipt URL, status, reviewer timestamp). |
| Real-time review | SSE `invoice_reviewed` (in addition to `purchase` on submit) | Open admin tabs refresh the queue immediately. |
| Review queue UI | `/admin/reviews` (`frontend/src/pages/AdminReviews.tsx`) | Receipt thumbnail → click for the full image, invoice, volunteer, partner, submitted time, Approve / Reject + optional reason. |
| Volunteer-facing split | `UserProfile.pending_reward_points`, profile page | `reward_points` is the **approved/spendable** balance; "Awaiting review" shows what is queued. Per-row `status`, and the volunteer is told *why* a receipt was rejected (`rejection_reason` on their own history only — never on the public per-business list). |
| Caps cannot be bypassed by queueing | `count_uses_today*` filter on `COUNTED_STATUSES` (`pending`, `approved`) | `pending` submissions consume a daily slot; a `rejected` one does **not** (an honest mistake shouldn't cost a volunteer their quota). |
| Migration for existing databases | `app/db/bootstrap.py::_ensure_review_columns` | Adds the six columns (guarded), creates the `status`/`receipt_sha256` indexes, and **backfills** every pre-existing row to `approved` with `reviewed_at = created_at`, so no historical reward is lost. |
| Rollout switch | `core/config.py::REQUIRE_RECEIPT_REVIEW: bool = True` | `False` restores Tier 1 exactly: receipt optional, instant credit. The JSON submit body is still accepted in that mode, so an older client keeps working. |

### Decisions taken for this tier

1. **Who reviews** — any authenticated admin. There is no separate reviewer
   role; every decision is attributable through `reviewed_by` + the audit row.
2. **SLA / reminders** — none automated in this tier. The queue is oldest-first
   and the dashboard shows an "Awaiting review" count.
3. **Re-submission after rejection** — **not allowed for the same invoice
   number**: the Tier 1 `UNIQUE(business_id, invoice_number)` guard stays, which
   is what stops a receipt being recycled. A rejected row also frees its daily
   slot so the volunteer can submit a *different*, correct invoice.
4. **Telling the volunteer why** — yes, the rejection reason is shown on their
   own history (it is never exposed on the public business history).

### Acceptance criteria

- A submission without a readable receipt cannot reach `approved` (the receipt
  is required while `REQUIRE_RECEIPT_REVIEW=True`).
- `reward_points` changes only through `approve_transaction` (or an admin
  manual adjustment), plus the documented Tier-1 fallback when
  `REQUIRE_RECEIPT_REVIEW=False`.
- Every approval is traceable to an admin id, a timestamp and an audit row.
- Legacy transactions are backfilled to `approved` (no rewards lost).
- The Tier 1 suite keeps passing with `REQUIRE_RECEIPT_REVIEW=False`.

**Honest limit:** Tier 2 makes fabrication expensive (a real-looking receipt
photo *and* a matching unused invoice number, once per partner) but a
determined volunteer can still photograph a genuine receipt and re-type its
number. Only Tier 3 makes fabrication impossible.

## Tier 3 — shipped (merchant single-use receipt codes)

Goal achieved for opted-in partners: a reward is now *authentic*, not merely
*proven*. An admin issues a batch of codes to a partner, the partner prints one
on each receipt, and the volunteer quotes it — a fabricated number simply never
matches an issued code.

| Control | Where | Effect |
| --- | --- | --- |
| Per-partner opt-in | `Business.codes_required` | Only a partner who actually prints codes requires one; everybody else keeps the Tier 1/2 flow untouched. |
| Single-use code inventory | `InvoiceCode` (`invoice_codes`), `services/invoice_codes.py` | `B28-XXXX-XXXX`, ambiguity-free (`secrets`), globally unique and bound to one partner. |
| Issue a batch | `POST /api/v1/admin/businesses/{id}/codes` | Mint up to 500 codes at once (optional batch label) and get them back to print. |
| Reconcile the sheet | `GET .../{id}/codes`, `GET .../{id}/codes/stats`, `DELETE /api/v1/admin/codes/{id}` | Paginated inventory by state, lifecycle counts, and revocation of an unclaimed code. |
| Code required at submission | `services/transactions.submit_invoice` (gate 0) | A `codes_required` partner refuses a submission with no code → 400 `invoice_code_required`. |
| Fabrication is impossible | `services/invoice_codes.claim_for_submission` | An unknown code, or one issued to another partner, is refused → 400 `invalid_invoice_code`. |
| One code, one reward | lifecycle `issued → claimed → redeemed` (`Transaction.code_id`) | Claimed on submission, redeemed on approval; the same code cannot back two live submissions → 409 `invoice_code_used`. |
| Honest mistakes don't burn a code | `reject_transaction` → `invoice_codes.release` | A rejected submission returns its code to `issued`, exactly as it frees the daily slot. |
| Migration for existing databases | `app/db/bootstrap.py::_ensure_code_columns` | Adds `businesses.codes_required` (default off) and `transactions.code_id`; the new `invoice_codes` table is built by `create_all`. |
| Admin UI | `/admin/businesses/{id}/codes` (`frontend/src/pages/AdminBusinessCodes.tsx`) | Generate, filter, print and revoke the codes for one partner. |

### Decisions taken for this tier

1. **Who is opted in** — the admin, per partner, via `codes_required`. Tier 3
   depends on the merchant printing codes, so a global switch would break every
   partner who cannot.
2. **Code vs invoice number** — the code is an *extra* field, not a replacement.
   The receipt's invoice number is still recorded, so Tier 1's per-partner
   duplicate guard keeps working alongside the code.
3. **Rejected submissions** — the code is released, matching the daily-cap rule:
   a blurry photo must not cost the volunteer the only code they have.
4. **Deleted partners** — `invoice_codes` cascades with the business and
   `transactions.code_id` is `SET NULL`, so reward history survives.

### Acceptance criteria

- A submission at a `codes_required` partner cannot reach `approved` without a
  valid, unused code issued to *that* partner.
- No code can be credited twice (`redeemed` is terminal).
- Every code is traceable to its partner, batch, volunteer and timestamps.
- A pre-Tier-3 database migrates with every partner left on the Tier 1/2 flow.
- The Tier 1/2 suite keeps passing.

**Honest limit:** Tier 3 makes fabrication impossible *only* while a code is
single-use and the partner keeps the sheet. A code photographed from an unused
receipt can still be quoted by someone else — the control bounds each printed
receipt to one reward, which is the property that matters. A **merchant
confirmation portal** (partner staff confirm the invoice in the customer's
presence) would close that last gap, but it needs every partner to log in, so it
remains deferred.
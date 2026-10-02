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

## Tier 2 — next milestone (real verification)

> **Execution plan:** the concrete, step-by-step build plan is in
> [`docs/NEXT_SESSION_TIER2.md`](./NEXT_SESSION_TIER2.md) — read that before
> starting this tier.

Goal: a reward is *proven*, not asserted.

1. **Receipt evidence**
   - Extend `InvoiceSubmitRequest` to a multipart submission: `business_id`,
     `invoice_number`, `receipt` (image/PDF).
   - Reuse the existing upload pipeline (`UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB`,
     `UnsupportedFileTypeError` / `FileTooLargeError`).

2. **Pending → approved lifecycle**
   - Add `Transaction.status` (`pending` / `approved` / `rejected`),
     `receipt_path`, `reviewed_by`, `reviewed_at`.
   - On submit: create the row as `pending`; **do not** touch
     `user.reward_points`.
   - New migration step in `app/db/bootstrap.py` for the added columns.

3. **Admin review**
   - `POST /admin/transactions/{id}/approve` and `.../reject`.
   - On approve: increment `reward_points` and write a `RewardAdjustment`
     audit row (the table already exists) — approvals must be auditable.
   - UI: a review queue in the admin dashboard, reusing the existing SSE
     `purchase` alert; show the receipt thumbnail beside the invoice number.

4. **Volunteer-facing**
   - Profile/history show `pending` vs `approved`, with the running **approved**
     balance as the spendable one.
   - BusinessDetail copy explains "your reward is credited after review".

5. **Anti-abuse for Tier 2**
   - Hash the receipt (e.g. SHA-256) and reject duplicate hashes per partner.
   - Rate-limit submissions per user per hour.

6. **Config & settings**
   - `REQUIRE_RECEIPT_REVIEW: bool = True` so a deployment can run Tier 1 only
     while partners are onboarded.

### Acceptance criteria

- A submission without a readable receipt cannot reach `approved`.
- `reward_points` changes only through `approve` (or an admin adjustment).
- Every approval is traceable to an admin id and timestamp.
- Existing Tier 1 tests keep passing with `REQUIRE_RECEIPT_REVIEW=False`.

## Tier 3 — strongest (requires partner cooperation)

- **Merchant one-time codes / QR**: an admin generates a batch of single-use
  codes per partner; each code is bound to that business and printed on the
  receipt. A fabricated number simply never matches an unused code. No merchant
  login needed.
- **Merchant confirmation portal**: partner staff confirm the invoice in the
  customer's presence.

Tier 3 is the only tier that makes fabrication *impossible* rather than merely
*impractical*, but it depends on partner participation, so it is deferred until
Tier 2 is live and partner appetite is known.
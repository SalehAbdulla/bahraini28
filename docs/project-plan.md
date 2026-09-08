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

### Phase 1: Project Setup & Database Models
- [ ] Initialize FastAPI project structure with virtual environment and dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `passlib[bcrypt]`, `python-jose`).
- [ ] Configure SQLAlchemy database engine and session management.
- [ ] Build database models: `Admin`, `User` (CPR, email, password_hash, expiry_date, first_login flag, token_version), `Business` (name, CR, logo_path, discount_percentage, expiry_date), `BusinessArea` (relationship table for multi-branch locations), and `Transaction` (user_id, business_id, invoice_number, timestamp, reward_increment).

### Phase 2: Authentication, Security & Middleware
- [ ] Implement secure password hashing utility using `passlib.bcrypt`.
- [ ] Create JWT token generation and validation dependencies with single-session tracking (`token_version` check).
- [ ] Build login endpoints for Users (supporting CPR or Email lookup, expiry date validation, and temporary password detection) and Admins.
- [ ] Implement profile-activation middleware/endpoint to force first-time users to update their name, email, and password.

### Phase 3: Admin Dashboard & Management APIs
- [ ] Develop Admin user-management endpoints (Add, Modify, Deactivate users, override expiry dates, and manual reward adjustments).
- [ ] Build detailed user analytics query (transaction history, aggregate metrics, most-frequented business).
- [ ] Implement master transaction log endpoint with pagination and real-time notification hooks.

### Phase 4: Business Directory & User Interface
- [ ] Create public landing page, login page (with "Volunteer Members Only" notice), and categorized business directory home page.
- [ ] Build individual business component view displaying logo, discount %, branch areas, and invoice submission form.
- [ ] Develop user profile view featuring member details, reward tracking cards, and transaction history.

### Phase 5: Frontend Polish & Testing
- [ ] Style all views using Tailwind CSS for clean, minimalist, mobile-friendly UX.
- [ ] Write integration tests for authentication flows, expiry checks, single-session token invalidation, and invoice reward increments.

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
- [ ] Add a condition in the transactions table to verify the number of times a business has been used, ensuring that it only counts purchases made **within the current calendar day**.

**Phase 3 & 4 (Business Page & Verification):**
- [ ] Program the verification system when a volunteer enters an invoice number: if they have reached 3 successful attempts at the same business during the same day, display a notice stating that the daily limit for this business has been exhausted, while still allowing purchases from other businesses.
- [ ] Ensure the system automatically resets the counter at the start of every new day.
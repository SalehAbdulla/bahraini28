// Type definitions mirroring the backend Pydantic schemas.

export interface UserProfile {
  id: number;
  cpr: string;
  email: string;
  name: string;
  phone: string | null;
  expiry_date: string;
  is_active: boolean;
  reward_points: number;
  /** Rewards waiting in the receipt-review queue (not spendable yet). */
  pending_reward_points: number;
  must_change_password: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: "user" | "admin";
  must_change_password: boolean;
}

export interface BusinessAreaOut {
  id: number;
  area_id: number;
  area_name: string;
  branch_name: string | null;
  address: string | null;
  phone: string | null;
}

export interface BusinessDetail {
  id: number;
  name: string;
  commercial_registration: string;
  logo_url: string | null;
  category_id: number;
  category_name: string;
  discount_percentage: number;
  /** Short headline replacing the percentage when the benefit is not a flat
   *  percentage (e.g. "Special offer"). */
  discount_label: string | null;
  description: string | null;
  invoice_pattern: string | null;
  /** True when this partner prints single-use codes (anti-fraud Tier 3). */
  codes_required: boolean;
  is_active: boolean;
  expiry_date: string;
  areas: BusinessAreaOut[];
}

export interface BusinessSummary {
  id: number;
  name: string;
  logo_url: string | null;
  category_name: string | null;
  discount_percentage: number;
  discount_label: string | null;
  areas: string[];
}

export interface CategoryOut {
  id: number;
  name: string;
  slug: string;
  description: string | null;
}

export interface AreaOut {
  id: number;
  name: string;
}

export interface AdminAreaOut extends AreaOut {
  is_active: boolean;
  created_at: string;
}

export interface AdminBusinessOut {
  id: number;
  name: string;
  commercial_registration: string;
  logo_url: string | null;
  category_id: number;
  category_name: string | null;
  discount_percentage: number;
  discount_label: string | null;
  description: string | null;
  invoice_pattern: string | null;
  codes_required: boolean;
  is_active: boolean;
  expiry_date: string;
  branches: Array<{
    id: number;
    area_id: number;
    area_name: string;
    branch_name: string | null;
    address: string | null;
    phone: string | null;
  }>;
  created_at: string;
  updated_at: string;
}

/** Receipt-review lifecycle (mirrors `models.transaction`). */
export type TransactionStatus = "pending" | "approved" | "rejected";

export interface TransactionOut {
  id: number;
  business_id: number;
  business_name: string;
  invoice_number: string;
  reward_increment: number;
  created_at: string;
  status: TransactionStatus;
  /** Tier 3 single-use receipt code, when the partner requires one. */
  code: string | null;
  /** Only ever populated on the volunteer's own history. */
  rejection_reason: string | null;
}

export interface TransactionCreatedOut extends TransactionOut {
  used_today: number;
  remaining_today: number;
  used_today_total: number;
  remaining_today_total: number;
  reward_points_balance: number;
}

export interface TransactionReviewOut extends TransactionOut {
  user_id: number;
  user_name: string;
  receipt_url: string | null;
  reviewed_at: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/** Lifecycle of a single-use merchant receipt code (anti-fraud Tier 3). */
export type InvoiceCodeStatus = "issued" | "claimed" | "redeemed" | "revoked";

export interface InvoiceCodeOut {
  id: number;
  business_id: number;
  code: string;
  status: InvoiceCodeStatus;
  batch: string | null;
  created_at: string;
  claimed_at: string | null;
  redeemed_at: string | null;
  claimed_by_user_id: number | null;
  claimed_by_user_name: string | null;
}

export interface InvoiceCodeBatchOut {
  items: InvoiceCodeOut[];
  created: number;
}

export interface InvoiceCodeStats {
  issued: number;
  claimed: number;
  redeemed: number;
  revoked: number;
  total: number;
}

export interface AdminUserOut extends UserProfile {
  total_transactions: number;
  total_rewards: number;
}

export interface DashboardMetrics {
  total_users: number;
  active_users: number;
  expired_users: number;
  total_businesses: number;
  total_transactions: number;
  transactions_today: number;
  total_rewards_awarded: number;
  /** Submissions waiting in the receipt-review queue (Tier 2). */
  pending_reviews: number;
  recent_transactions: Array<{
    id: number;
    user_id: number;
    user_name: string | null;
    business_id: number;
    business_name: string | null;
    invoice_number: string;
    reward_increment: number;
    status: TransactionStatus;
    created_at: string;
  }>;
}

export interface UserAnalytics {
  user: UserProfile;
  total_transactions: number;
  total_rewards_today: number;
  total_rewards_all_time: number;
  most_frequented_business: {
    business_id: number;
    business_name: string;
    category_name: string | null;
    count: number;
  } | null;
  favorite_category: string | null;
  last_activity: string | null;
  recent_transactions: Array<{
    id: number;
    business_id: number;
    business_name: string | null;
    invoice_number: string;
    reward_increment: number;
    created_at: string;
  }>;
}

export interface ApiError {
  detail: string;
  code?: string;
  status?: number;
}
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
  description: string | null;
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

export interface AdminBusinessOut {
  id: number;
  name: string;
  commercial_registration: string;
  logo_url: string | null;
  category_id: number;
  category_name: string | null;
  discount_percentage: number;
  description: string | null;
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

export interface TransactionOut {
  id: number;
  business_id: number;
  business_name: string;
  invoice_number: string;
  reward_increment: number;
  created_at: string;
}

export interface TransactionCreatedOut extends TransactionOut {
  used_today: number;
  remaining_today: number;
  reward_points_balance: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
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
  recent_transactions: Array<{
    id: number;
    user_id: number;
    user_name: string | null;
    business_id: number;
    business_name: string | null;
    invoice_number: string;
    reward_increment: number;
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
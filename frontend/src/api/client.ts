import type { ApiError } from "../types";

/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * - Tokens are kept in localStorage (user vs admin, matching the backend's
 *   role-split single-session model).
 * - All responses are JSON; errors are normalized to `ApiError`.
 */

// Defaults to the same-origin API prefix so the Vite dev proxy (/api → :8000)
// and the production reverse proxy (/api/* → backend) both work without any
// per-environment configuration. Override with VITE_API_URL for odd setups.
const API_URL = (import.meta.env.VITE_API_URL as string | undefined) || "/api/v1";
const USER_TOKEN_KEY = "be_user_token";
const ADMIN_TOKEN_KEY = "be_admin_token";

export function getUserToken(): string | null {
  return localStorage.getItem(USER_TOKEN_KEY);
}
export function setUserToken(token: string | null): void {
  if (token === null) localStorage.removeItem(USER_TOKEN_KEY);
  else localStorage.setItem(USER_TOKEN_KEY, token);
}
export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}
export function setAdminToken(token: string | null): void {
  if (token === null) localStorage.removeItem(ADMIN_TOKEN_KEY);
  else localStorage.setItem(ADMIN_TOKEN_KEY, token);
}
export function clearTokens(): void {
  localStorage.removeItem(USER_TOKEN_KEY);
  localStorage.removeItem(ADMIN_TOKEN_KEY);
}

export class RequestError extends Error implements ApiError {
  status: number;
  code?: string;
  detail: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "RequestError";
    this.status = status;
    this.code = code;
    this.detail = message;
  }
}

interface ApiOptions {
  method?: string;
  body?: unknown;
  admin?: boolean;
  auth?: boolean;
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = opts.admin ? getAdminToken() : getUserToken();
  if (opts.auth !== false && token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const detail =
      (data as { detail?: string } | null)?.detail ?? `Request failed (${res.status})`;
    const code = (data as { code?: string } | null)?.code;
    if (res.status === 401 && !opts.admin) {
      setUserToken(null);
    }
    throw new RequestError(detail, res.status, code);
  }

  return data as T;
}
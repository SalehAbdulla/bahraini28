import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, RequestError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { fmtDate } from "./BusinessDetail";
import type { DashboardMetrics } from "../types";

interface PurchaseAlert {
  transaction_id: number;
  user_name: string | null;
  business_name: string | null;
  invoice_number: string;
  reward_increment: number;
  status: string;
  created_at: string;
}

export default function AdminDashboard() {
  const { adminToken, adminLogout } = useAuth();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [alerts, setAlerts] = useState<PurchaseAlert[]>([]);
  const [feedStatus, setFeedStatus] = useState("Connecting…");

  const load = useCallback(() => {
    api<DashboardMetrics>("/admin/metrics", { admin: true })
      .then(setMetrics)
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Real-time purchase alert feed via SSE (token passed as query param).
  useEffect(() => {
    if (!adminToken) return;
    const url = `/api/v1/admin/notifications/stream?_token=${encodeURIComponent(adminToken)}`;
    const es = new EventSource(url);

    es.addEventListener("connected", () => {
      setFeedStatus("Live. Waiting for purchases…");
    });
    es.addEventListener("purchase", (ev) => {
      try {
        const data = JSON.parse(ev.data) as PurchaseAlert;
        setAlerts((prev) => [data, ...prev].slice(0, 50));
        setFeedStatus("Live.");
      } catch {
        /* ignore malformed frames */
      }
    });
    es.onerror = () => setFeedStatus("Connection interrupted — reconnecting…");

    return () => es.close();
  }, [adminToken]);

  // --- change own password (anti-lockout: the current one is re-verified) -----
  const [pwOpen, setPwOpen] = useState(false);
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [pwError, setPwError] = useState("");
  const [pwNotice, setPwNotice] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  const closePassword = () => {
    setPwOpen(false);
    setPwCurrent("");
    setPwNew("");
    setPwConfirm("");
    setPwError("");
    setPwNotice("");
  };

  const submitPassword = async (e: FormEvent) => {
    e.preventDefault();
    setPwError("");
    setPwNotice("");
    if (pwNew.length < 8) {
      setPwError("The new password must be at least 8 characters.");
      return;
    }
    if (pwNew !== pwConfirm) {
      setPwError("The two new passwords do not match.");
      return;
    }
    setPwBusy(true);
    try {
      await api("/admin/me/password", {
        method: "POST",
        admin: true,
        body: { current_password: pwCurrent, new_password: pwNew },
      });
      setPwCurrent("");
      setPwNew("");
      setPwConfirm("");
      setPwNotice("Password updated — use it the next time you sign in.");
    } catch (err) {
      setPwError(
        err instanceof RequestError ? err.message : "Could not change the password."
      );
    } finally {
      setPwBusy(false);
    }
  };

  const tiles: Array<{ label: string; value: number; cls: string }> = metrics
    ? [
        { label: "Total users", value: metrics.total_users, cls: "text-slate-900" },
        { label: "Active users", value: metrics.active_users, cls: "text-brand-600" },
        { label: "Expired", value: metrics.expired_users, cls: "text-red-600" },
        { label: "Transactions today", value: metrics.transactions_today, cls: "text-blue-600" },
        { label: "All transactions", value: metrics.total_transactions, cls: "text-slate-900" },
        { label: "Businesses", value: metrics.total_businesses, cls: "text-slate-900" },
        { label: "Rewards awarded", value: metrics.total_rewards_awarded, cls: "text-amber-600" },
        { label: "Awaiting review", value: metrics.pending_reviews, cls: "text-brand-600" },
      ]
    : [];

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900">Admin Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            Global overview &amp; real-time purchase alerts.
          </p>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <Link to="/admin/reviews" className="btn-secondary">Receipt review</Link>
          <Link to="/admin/users" className="btn-secondary">Users</Link>
          <Link to="/admin/businesses" className="btn-secondary">Businesses</Link>
          <Link to="/admin/catalog" className="btn-secondary">Areas &amp; Categories</Link>
          <Link to="/admin/transactions" className="btn-secondary">Ledger</Link>
          <button onClick={() => setPwOpen(true)} className="btn-secondary">
            Change password
          </button>
          <button onClick={adminLogout} className="btn-secondary">Sign out</button>
        </div>
      </div>

      {tiles.length > 0 && (
        <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4">
          {tiles.map((t) => (
            <div key={t.label} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {t.label}
              </div>
              <div className={`mt-1 text-3xl font-extrabold ${t.cls}`}>{t.value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-10 grid lg:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h2 className="font-semibold text-slate-900 mb-4">Real-time purchase alerts</h2>
          <div className="space-y-2 text-sm max-h-96 overflow-y-auto">
            {alerts.length === 0 ? (
              <p className="text-slate-400">No alerts yet.</p>
            ) : (
              alerts.map((a) => (
                <div
                  key={a.transaction_id}
                  className="flex items-start gap-3 bg-brand-50 border border-brand-200 rounded-xl px-3 py-2"
                >
                  <span className="text-lg">🛍️</span>
                  <div>
                    <div className="font-medium text-slate-800">
                      {a.user_name ?? "Member"} used {a.business_name ?? "a partner"}
                    </div>
                    <div className="text-xs text-slate-500">
                      Invoice {a.invoice_number} · +{a.reward_increment} ·{" "}
                      {fmtDate(a.created_at)}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
          <div className="mt-3 text-xs text-slate-400">{feedStatus}</div>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h2 className="font-semibold text-slate-900 mb-4">Recent transactions</h2>
          {metrics?.recent_transactions.length ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-slate-500">
                  <th className="px-3 py-2">User</th>
                  <th className="px-3 py-2">Business</th>
                  <th className="px-3 py-2">Invoice</th>
                  <th className="px-3 py-2">When</th>
                </tr>
              </thead>
              <tbody>
                {metrics.recent_transactions.map((t) => (
                  <tr key={t.id} className="border-t border-slate-100">
                    <td className="px-3 py-2">{t.user_name}</td>
                    <td className="px-3 py-2">{t.business_name}</td>
                    <td className="px-3 py-2">{t.invoice_number}</td>
                    <td className="px-3 py-2">{fmtDate(t.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-slate-400 text-sm">No transactions yet.</p>
          )}
        </div>
      </div>

      {pwOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 shadow-lg p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Change password</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Your current password is required. Other open admin tabs stay signed in.
                </p>
              </div>
              <button type="button" className="btn-secondary" onClick={closePassword}>
                ✕
              </button>
            </div>
            <form onSubmit={submitPassword} className="mt-4 space-y-3">
              <div>
                <label htmlFor="pw-current" className="block text-sm font-medium text-slate-700">
                  Current password
                </label>
                <input
                  id="pw-current"
                  type="password"
                  className="input-field mt-1"
                  autoComplete="current-password"
                  required
                  value={pwCurrent}
                  onChange={(e) => setPwCurrent(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="pw-new" className="block text-sm font-medium text-slate-700">
                  New password
                </label>
                <input
                  id="pw-new"
                  type="password"
                  className="input-field mt-1"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  maxLength={72}
                  value={pwNew}
                  onChange={(e) => setPwNew(e.target.value)}
                />
                <p className="mt-1 text-xs text-slate-500">At least 8 characters.</p>
              </div>
              <div>
                <label htmlFor="pw-confirm" className="block text-sm font-medium text-slate-700">
                  Repeat the new password
                </label>
                <input
                  id="pw-confirm"
                  type="password"
                  className="input-field mt-1"
                  autoComplete="new-password"
                  required
                  value={pwConfirm}
                  onChange={(e) => setPwConfirm(e.target.value)}
                />
              </div>
              {pwError && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {pwError}
                </div>
              )}
              {pwNotice && (
                <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                  {pwNotice}
                </div>
              )}
              <div className="flex gap-3">
                <button type="submit" className="btn-primary" disabled={pwBusy}>
                  {pwBusy ? "Saving…" : "Update password"}
                </button>
                <button type="button" className="btn-secondary" onClick={closePassword}>
                  Close
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
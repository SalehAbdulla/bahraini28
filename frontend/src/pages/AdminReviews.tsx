import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RequestError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Pagination from "../components/Pagination";
import StatusPill from "../components/StatusPill";
import { fmtDate } from "./BusinessDetail";
import type { Page, TransactionReviewOut } from "../types";

const FILTERS = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];

export default function AdminReviews() {
  const { adminToken } = useAuth();
  const [items, setItems] = useState<TransactionReviewOut[]>([]);
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [reasonFor, setReasonFor] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(
    async (p = 1, s = status) => {
      const params = new URLSearchParams({ status: s, page: String(p), page_size: "12" });
      try {
        const data = await api<Page<TransactionReviewOut>>(
          `/admin/transactions/review?${params.toString()}`,
          { admin: true }
        );
        setItems(data.items);
        setPages(data.pages);
        setPage(data.page);
      } catch {
        /* auth-guard handles redirect */
      }
    },
    [status]
  );

  useEffect(() => {
    load(1);
  }, [load]);

  // Another tab (or a volunteer) may add/decide submissions — refresh on the
  // shared SSE feed so the queue never shows a stale decision.
  useEffect(() => {
    if (!adminToken) return;
    const url = `/api/v1/admin/notifications/stream?_token=${encodeURIComponent(adminToken)}`;
    const es = new EventSource(url);
    const refresh = () => load(1);
    es.addEventListener("purchase", refresh);
    es.addEventListener("invoice_reviewed", refresh);
    return () => es.close();
  }, [adminToken, load]);

  const decide = async (
    t: TransactionReviewOut,
    action: "approve" | "reject",
    why?: string
  ) => {
    setBusyId(t.id);
    setError("");
    try {
      await api(`/admin/transactions/${t.id}/${action}`, {
        method: "POST",
        admin: true,
        body: action === "reject" ? { reason: (why ?? "").trim() || null } : {},
      });
      setReasonFor(null);
      setReason("");
      await load(page);
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "Review failed.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-600/80">
            Admin · control centre
          </p>
          <h1 className="mt-2 font-serif text-3xl font-normal tracking-[-0.015em] text-ink-900">
            Receipt review
          </h1>
          <p className="mt-1 text-sm text-ink-800/60">
            A reward is credited only once you approve the receipt.
          </p>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <Link to="/admin" className="btn-secondary">
            Dashboard
          </Link>
          <Link to="/admin/transactions" className="btn-secondary">
            Ledger
          </Link>
        </div>
      </div>

      <div className="mt-6 flex gap-2 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setStatus(f.value)}
            className={status === f.value ? "btn-primary" : "btn-secondary"}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <div className="mt-6 bg-white border border-ink-900/10 rounded-2xl overflow-x-auto">
        {items.length === 0 ? (
          <p className="p-4 text-sm text-ink-800/50">Nothing waiting.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-ink-900/5 text-left text-ink-800/60">
                <th className="px-4 py-2">Receipt</th>
                <th className="px-4 py-2">Invoice</th>
                <th className="px-4 py-2">Volunteer</th>
                <th className="px-4 py-2">Partner</th>
                <th className="px-4 py-2">Submitted</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Decision</th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => (
                <tr key={t.id} className="border-t border-ink-900/10 align-top">
                  <td className="px-4 py-2">
                    {t.receipt_url ? (
                      <a
                        href={t.receipt_url}
                        target="_blank"
                        rel="noreferrer"
                        title="Open the full receipt"
                      >
                        <img
                          src={t.receipt_url}
                          alt={`Receipt for ${t.invoice_number}`}
                          className="h-12 w-12 border border-ink-900/15 object-cover"
                        />
                      </a>
                    ) : (
                      <span className="text-ink-800/40">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2 font-mono font-semibold text-ink-900">
                    {t.invoice_number}
                  </td>
                  <td className="px-4 py-2">{t.user_name}</td>
                  <td className="px-4 py-2">{t.business_name}</td>
                  <td className="px-4 py-2 whitespace-nowrap">{fmtDate(t.created_at)}</td>
                  <td className="px-4 py-2">
                    <StatusPill status={t.status} />
                    {t.rejection_reason && (
                      <span className="mt-1 block text-xs text-ink-800/60">
                        {t.rejection_reason}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    {t.status !== "pending" ? (
                      <span className="text-xs text-ink-800/50">
                        {t.reviewed_at ? `Reviewed ${fmtDate(t.reviewed_at)}` : "—"}
                      </span>
                    ) : reasonFor === t.id ? (
                      <div className="flex min-w-[200px] flex-col gap-2">
                        <input
                          className="input-field"
                          placeholder="Reason (optional)"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                        />
                        <div className="flex gap-2">
                          <button
                            type="button"
                            className="btn-primary"
                            disabled={busyId === t.id}
                            onClick={() => decide(t, "reject", reason)}
                          >
                            Confirm reject
                          </button>
                          <button
                            type="button"
                            className="btn-secondary"
                            onClick={() => {
                              setReasonFor(null);
                              setReason("");
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          className="btn-primary"
                          disabled={busyId === t.id}
                          onClick={() => decide(t, "approve")}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={busyId === t.id}
                          onClick={() => {
                            setReasonFor(t.id);
                            setReason("");
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Pagination page={page} pages={pages} onPage={(p) => load(p)} />
    </>
  );
}

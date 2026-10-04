import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, RequestError } from "../api/client";
import Pagination from "../components/Pagination";
import { fmtDate } from "./BusinessDetail";
import type {
  BusinessDetail as BusinessDetailType,
  InvoiceCodeBatchOut,
  InvoiceCodeOut,
  InvoiceCodeStats,
  InvoiceCodeStatus,
  Page,
} from "../types";

const FILTERS = [
  { value: "issued", label: "Available" },
  { value: "claimed", label: "Claimed" },
  { value: "redeemed", label: "Redeemed" },
  { value: "revoked", label: "Revoked" },
  { value: "all", label: "All" },
];

// Sharp-cornered pills in the existing brand/ink/red tokens — no new palette.
const CODE_STYLES: Record<InvoiceCodeStatus, string> = {
  issued: "border-brand-200 bg-brand-50 text-brand-700",
  claimed: "border-ink-900/15 bg-ink-900/5 text-ink-800",
  redeemed: "border-ink-900/15 bg-ink-900/10 text-ink-900",
  revoked: "border-red-200 bg-red-50 text-red-700",
};

export default function AdminBusinessCodes() {
  const { id } = useParams<{ id: string }>();
  const businessId = Number(id);

  const [business, setBusiness] = useState<BusinessDetailType | null>(null);
  const [stats, setStats] = useState<InvoiceCodeStats | null>(null);
  const [items, setItems] = useState<InvoiceCodeOut[]>([]);
  const [status, setStatus] = useState("issued");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);

  const [count, setCount] = useState("10");
  const [batch, setBatch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api<BusinessDetailType>(`/businesses/${businessId}`)
      .then(setBusiness)
      .catch(() => {});
  }, [businessId]);

  const loadStats = useCallback(async () => {
    try {
      const data = await api<InvoiceCodeStats>(
        `/admin/businesses/${businessId}/codes/stats`,
        { admin: true }
      );
      setStats(data);
    } catch {
      /* auth-guard handles redirect */
    }
  }, [businessId]);

  const load = useCallback(
    async (p = 1, s = status) => {
      const params = new URLSearchParams({ status: s, page: String(p), page_size: "20" });
      try {
        const data = await api<Page<InvoiceCodeOut>>(
          `/admin/businesses/${businessId}/codes?${params.toString()}`,
          { admin: true }
        );
        setItems(data.items);
        setPages(data.pages);
        setPage(data.page);
      } catch {
        /* auth-guard handles redirect */
      }
    },
    [businessId, status]
  );

  useEffect(() => {
    load(1);
    loadStats();
  }, [load, loadStats]);

  const generate = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    const n = Number(count);
    if (!Number.isFinite(n) || n < 1 || n > 500) {
      setError("Enter a batch size between 1 and 500 codes.");
      return;
    }
    setBusy(true);
    try {
      const res = await api<InvoiceCodeBatchOut>(
        `/admin/businesses/${businessId}/codes`,
        { method: "POST", admin: true, body: { count: n, batch: batch.trim() || null } }
      );
      setNotice(`Generated ${res.created} single-use code(s).`);
      setBatch("");
      await Promise.all([load(1), loadStats()]);
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "Could not generate codes.");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (c: InvoiceCodeOut) => {
    if (!window.confirm(`Revoke ${c.code}? This cannot be undone.`)) return;
    setError("");
    setNotice("");
    try {
      await api(`/admin/codes/${c.id}`, { method: "DELETE", admin: true });
      await Promise.all([load(page), loadStats()]);
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "Revoke failed.");
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
            Receipt codes
          </h1>
          <p className="mt-1 text-sm text-ink-800/60">
            {business ? business.name : "Loading…"} · single-use codes that make a fabricated
            invoice impossible.
          </p>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <Link to="/admin/businesses" className="btn-secondary">
            Businesses
          </Link>
          <Link to="/admin" className="btn-secondary">
            Dashboard
          </Link>
        </div>
      </div>

      {stats && (
        <div className="mt-8 grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[
            { label: "Total", value: stats.total },
            { label: "Available", value: stats.issued },
            { label: "Claimed", value: stats.claimed },
            { label: "Redeemed", value: stats.redeemed },
            { label: "Revoked", value: stats.revoked },
          ].map((t) => (
            <div key={t.label} className="bg-white border border-ink-900/10 rounded-2xl p-5">
              <div className="text-xs font-semibold uppercase tracking-wide text-ink-800/50">
                {t.label}
              </div>
              <div className="mt-1 font-serif text-3xl text-ink-900">{t.value}</div>
            </div>
          ))}
        </div>
      )}

      {business && !business.codes_required && (
        <p className="mt-6 text-sm text-ink-800/70 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          This partner is not set to require codes yet. Codes are ignored until you tick
          “Require a single-use receipt code” on the partner's record.
        </p>
      )}

      <div className="mt-6 bg-white border border-ink-900/10 rounded-2xl p-6">
        <h2 className="font-serif text-xl font-normal text-ink-900">Generate a batch</h2>
        <p className="mt-1 text-sm text-ink-800/70">
          Mint single-use codes and print them on this partner's receipts. Each code credits one
          invoice, once.
        </p>
        <form onSubmit={generate} className="mt-4 flex gap-3 flex-wrap items-end">
          <div>
            <label htmlFor="code-count" className="block text-sm font-medium text-ink-800">
              How many
            </label>
            <input
              id="code-count"
              type="number"
              min={1}
              max={500}
              className="input-field mt-1 w-32"
              value={count}
              onChange={(e) => setCount(e.target.value)}
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="code-batch" className="block text-sm font-medium text-ink-800">
              Batch label (optional)
            </label>
            <input
              id="code-batch"
              className="input-field mt-1"
              placeholder="e.g. sheet-2026-01"
              maxLength={60}
              value={batch}
              onChange={(e) => setBatch(e.target.value)}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Generating…" : "Generate codes"}
          </button>
        </form>
        {notice && (
          <div className="mt-3 text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 text-sm">
            {notice}
          </div>
        )}
        {error && (
          <div className="mt-3 text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm">
            {error}
          </div>
        )}
      </div>

      <div className="mt-6 flex gap-2 flex-wrap">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            className={f.value === status ? "btn-primary" : "btn-secondary"}
            onClick={() => {
              setStatus(f.value);
              load(1, f.value);
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="mt-4 bg-white border border-ink-900/10 rounded-2xl overflow-x-auto">
        {items.length === 0 ? (
          <p className="p-4 text-sm text-ink-800/50">No codes in this state.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-ink-900/5 text-left text-ink-800/60">
                <th className="px-4 py-2">Code</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Batch</th>
                <th className="px-4 py-2">Created</th>
                <th className="px-4 py-2">Used by</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-t border-ink-900/10">
                  <td className="px-4 py-2 font-mono font-semibold text-ink-900">{c.code}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${CODE_STYLES[c.status]}`}
                    >
                      {c.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-ink-800/60">{c.batch ?? "—"}</td>
                  <td className="px-4 py-2 whitespace-nowrap">{fmtDate(c.created_at)}</td>
                  <td className="px-4 py-2">{c.claimed_by_user_name ?? "—"}</td>
                  <td className="px-4 py-2 text-right">
                    {c.status === "issued" ? (
                      <button type="button" className="btn-secondary" onClick={() => revoke(c)}>
                        Revoke
                      </button>
                    ) : (
                      <span className="text-xs text-ink-800/40">—</span>
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

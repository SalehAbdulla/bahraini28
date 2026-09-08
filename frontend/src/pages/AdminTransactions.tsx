import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { fmtDate } from "./BusinessDetail";
import Pagination from "../components/Pagination";
import type { Page, TransactionOut } from "../types";

export default function AdminTransactions() {
  const [items, setItems] = useState<TransactionOut[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [search, setSearch] = useState("");
  const [userId, setUserId] = useState("");
  const [businessId, setBusinessId] = useState("");

  const load = useCallback(async (p = 1, s = search, u = userId, b = businessId) => {
    const params = new URLSearchParams({ page: String(p), page_size: "15" });
    if (s.trim()) params.set("search", s.trim());
    if (u.trim()) params.set("user_id", u.trim());
    if (b.trim()) params.set("business_id", b.trim());
    try {
      const data = await api<Page<TransactionOut>>(
        `/admin/transactions?${params.toString()}`,
        { admin: true }
      );
      setItems(data.items);
      setPages(data.pages);
      setPage(data.page);
    } catch {
      /* auth-guard handles redirect */
    }
  }, [search, userId, businessId]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(1), 250);
    return () => clearTimeout(t);
  }, [search, userId, businessId, load]);

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900">Transaction Ledger</h1>
          <p className="mt-1 text-sm text-slate-500">
            Master record of every invoice submission.
          </p>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <Link to="/admin" className="btn-secondary">Dashboard</Link>
          <Link to="/admin/users" className="btn-secondary">Users</Link>
        </div>
      </div>

      <div className="mt-6 flex gap-2 flex-wrap">
        <input
          className="input-field"
          placeholder="Search invoice / business…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <input
          className="input-field w-28"
          type="number"
          min={1}
          placeholder="User ID"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
        />
        <input
          className="input-field w-32"
          type="number"
          min={1}
          placeholder="Business ID"
          value={businessId}
          onChange={(e) => setBusinessId(e.target.value)}
        />
      </div>

      <div className="mt-6 bg-white border border-slate-200 rounded-2xl overflow-x-auto">
        {items.length === 0 ? (
          <p className="p-4 text-sm text-slate-400">No transactions yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-slate-500">
                <th className="px-4 py-2">Invoice #</th>
                <th className="px-4 py-2">Business</th>
                <th className="px-4 py-2">Reward</th>
                <th className="px-4 py-2">When</th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => (
                <tr key={t.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 font-mono font-semibold">{t.invoice_number}</td>
                  <td className="px-4 py-2">{t.business_name}</td>
                  <td className="px-4 py-2">+{t.reward_increment}</td>
                  <td className="px-4 py-2">{fmtDate(t.created_at)}</td>
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
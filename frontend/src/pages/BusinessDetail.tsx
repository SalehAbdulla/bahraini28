import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, RequestError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type {
  BusinessDetail as BusinessDetailType,
  Page,
  TransactionCreatedOut,
  TransactionOut,
} from "../types";

export default function BusinessDetail() {
  const { id } = useParams<{ id: string }>();
  const businessId = Number(id);
  const navigate = useNavigate();
  const { isUser } = useAuth();

  const [business, setBusiness] = useState<BusinessDetailType | null>(null);
  const [history, setHistory] = useState<TransactionOut[]>([]);
  const [notFound, setNotFound] = useState(false);

  const [invoice, setInvoice] = useState("");
  const [result, setResult] = useState<TransactionCreatedOut | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<BusinessDetailType>(`/businesses/${businessId}`)
      .then(setBusiness)
      .catch(() => setNotFound(true));
    api<Page<TransactionOut>>(`/businesses/${businessId}/transactions?page_size=10`)
      .then((d) => setHistory(d.items))
      .catch(() => {});
  }, [businessId]);

  const submitInvoice = async (e: FormEvent) => {
    e.preventDefault();
    if (!isUser) {
      navigate("/login");
      return;
    }
    setError("");
    setResult(null);
    setBusy(true);
    try {
      const res = await api<TransactionCreatedOut>("/transactions", {
        method: "POST",
        body: { business_id: businessId, invoice_number: invoice.trim() },
      });
      setResult(res);
      setInvoice("");
      setHistory((prev) => [
        {
          id: res.id,
          business_id: res.business_id,
          business_name: res.business_name,
          invoice_number: res.invoice_number,
          reward_increment: res.reward_increment,
          created_at: res.created_at,
        },
        ...prev,
      ]);
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "Submission failed.");
    } finally {
      setBusy(false);
    }
  };

  if (notFound) {
    return <p className="text-ink-800/50 py-16 text-center">Business not found.</p>;
  }
  if (!business) {
    return <p className="text-ink-800/50 py-16 text-center">Loading…</p>;
  }

  return (
    <div className="max-w-4xl">
      <div className="bg-white border border-ink-900/10 rounded-2xl p-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-4">
            {business.logo_url && (
              <img
                src={business.logo_url}
                alt={business.name}
                className="h-16 w-16 object-contain rounded-lg border border-ink-900/10"
              />
            )}
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-600/80">
                Partner
              </p>
              <h1 className="mt-2 font-serif text-3xl font-normal tracking-[-0.015em] text-ink-900">
                {business.name}
              </h1>
              <p className="mt-1 text-sm text-ink-800/60">
                {business.category_name} · CR {business.commercial_registration}
              </p>
            </div>
          </div>
          <span className="inline-block text-sm font-semibold px-3 py-1 bg-brand-100 text-brand-700">
            -{business.discount_percentage}% discount
          </span>
        </div>
        <p className="mt-4 text-ink-800/70">
          {business.description ?? "No description provided."}
        </p>
        <div className="mt-5">
          <h3 className="mb-2 font-serif text-lg font-normal text-ink-900">
            Active areas / branches
          </h3>
          <ul className="text-sm text-ink-800/70 space-y-1">
            {business.areas.map((a) => (
              <li key={a.id}>
                📍 {a.area_name}
                {a.branch_name ? ` — ${a.branch_name}` : ""}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-6 bg-white border border-ink-900/10 rounded-2xl p-6">
        <h2 className="font-serif text-xl font-normal text-ink-900">Submit an invoice</h2>
        <p className="mt-1 text-sm text-ink-800/70">
          Enter the invoice number from your physical receipt to earn a reward.
          Each invoice can be credited once, and there is a daily cap per partner
          and overall (resets at midnight).
        </p>
        <form onSubmit={submitInvoice} className="mt-4 flex gap-3 flex-wrap">
          <input
            className="input-field flex-1 min-w-[220px]"
            placeholder="Invoice number"
            required
            minLength={3}
            maxLength={64}
            value={invoice}
            onChange={(e) => setInvoice(e.target.value)}
          />
          <button type="submit" disabled={busy} className="btn-primary">
            {busy ? "Submitting…" : "Submit invoice"}
          </button>
        </form>
        {result && (
          <div className="mt-3 text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 text-sm">
            ✅ Invoice verified! +{result.reward_increment} reward ·{" "}
            {result.remaining_today} uses left today here ·{" "}
            {result.remaining_today_total} left today overall.
          </div>
        )}
        {error && (
          <div className="mt-3 text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm">
            ❌ {error}
          </div>
        )}
      </div>
      <h2 className="mt-8 font-serif text-xl font-normal text-ink-900">
        Public transaction history
      </h2>
      <div className="mt-3 bg-white border border-ink-900/10 rounded-2xl overflow-hidden">
        {history.length === 0 ? (
          <p className="p-4 text-sm text-ink-800/50">No transactions yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-ink-900/5 text-left text-ink-800/60">
                <th className="px-4 py-2">Invoice</th>
                <th className="px-4 py-2">Reward</th>
                <th className="px-4 py-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {history.map((t) => (
                <tr key={t.id} className="border-t border-ink-900/10">
                  <td className="px-4 py-2">{t.invoice_number}</td>
                  <td className="px-4 py-2">+{t.reward_increment}</td>
                  <td className="px-4 py-2">{fmtDate(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function fmtDateOnly(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}
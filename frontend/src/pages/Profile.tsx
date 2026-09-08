import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { fmtDate, fmtDateOnly } from "./BusinessDetail";
import type { Page, TransactionOut, UserProfile } from "../types";

export default function Profile() {
  const { profile, logout, refreshProfile } = useAuth();
  const [me, setMe] = useState<UserProfile | null>(profile);
  const [history, setHistory] = useState<TransactionOut[]>([]);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [saved, setSaved] = useState(false);
  const [editError, setEditError] = useState("");

  useEffect(() => {
    refreshProfile().then(() => {});
  }, [refreshProfile]);

  const load = useCallback(async () => {
    try {
      const meData = await api<UserProfile>("/users/me");
      setMe(meData);
      setName(meData.name);
      setEmail(meData.email);
      setPhone(meData.phone ?? "");
      const tx = await api<Page<TransactionOut>>("/users/me/transactions?page_size=10");
      setHistory(tx.items);
    } catch {
      /* auth-guard handles redirect */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    setEditError("");
    setSaved(false);
    try {
      await api("/users/me", {
        method: "PATCH",
        body: { name: name.trim(), email: email.trim(), phone: phone.trim() },
      });
      setSaved(true);
      await refreshProfile();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Update failed.");
    }
  };

  if (!me) return <p className="text-slate-400 py-16 text-center">Loading…</p>;

  const cards = [
    { label: "Reward points", value: me.reward_points, cls: "text-brand-600" },
    { label: "Membership", value: me.is_active ? "Active" : "Inactive", cls: "text-brand-600" },
    { label: "Expires", value: fmtDateOnly(me.expiry_date), cls: "text-slate-600" },
  ];

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900">{me.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            CPR {me.cpr} · {me.is_active ? "Active member" : "Inactive account"}
          </p>
        </div>
        <button onClick={logout} className="btn-secondary sm:ml-auto">
          Sign out
        </button>
      </div>

      <div className="mt-8 grid sm:grid-cols-3 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {c.label}
            </div>
            <div className={`mt-1 text-2xl font-extrabold ${c.cls}`}>{c.value}</div>
          </div>
        ))}
      </div>

      <div className="mt-8 grid md:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h2 className="font-semibold text-slate-900 mb-4">Membership details</h2>
          <dl className="space-y-3 text-sm">
            {[
              ["Name", me.name],
              ["CPR", me.cpr],
              ["Email", me.email],
              ["Phone", me.phone || "—"],
              ["Reward points", me.reward_points],
              ["Membership expiry", fmtDate(me.expiry_date)],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b border-slate-100 pb-2">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-medium text-slate-900">{v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <h2 className="font-semibold text-slate-900 mb-4">Edit profile</h2>
          <form onSubmit={saveProfile} className="space-y-4" noValidate>
            <div>
              <label className="block text-sm font-medium text-slate-700">Full name</label>
              <input className="input-field" required minLength={2} maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Email</label>
              <input type="email" className="input-field" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Phone</label>
              <input type="tel" className="input-field" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>
            {saved && (
              <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                Saved.
              </div>
            )}
            {editError && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {editError}
              </div>
            )}
            <button type="submit" className="btn-primary">Save changes</button>
          </form>
        </div>
      </div>

      <h2 className="mt-12 text-xl font-bold text-slate-900">My usage history</h2>
      <div className="mt-4 bg-white border border-slate-200 rounded-2xl overflow-hidden">
        {history.length === 0 ? (
          <p className="p-4 text-sm text-slate-400">
            No transactions yet — visit the directory and submit your first invoice!
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-slate-500">
                <th className="px-4 py-2">Business</th>
                <th className="px-4 py-2">Invoice</th>
                <th className="px-4 py-2">Reward</th>
                <th className="px-4 py-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {history.map((t) => (
                <tr key={t.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">{t.business_name}</td>
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
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { fmtDateOnly } from "./BusinessDetail";
import Pagination from "../components/Pagination";
import type { AdminUserOut, Page } from "../types";

interface UserFormState {
  id: number | null;
  cpr: string;
  email: string;
  name: string;
  phone: string;
  expiry: string;
  password: string;
  rewards: number;
}

const EMPTY_FORM: UserFormState = {
  id: null,
  cpr: "",
  email: "",
  name: "",
  phone: "",
  expiry: "",
  password: "",
  rewards: 0,
};

function toLocalInput(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AdminUsers() {
  const [items, setItems] = useState<AdminUserOut[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<UserFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState("");

  const load = useCallback(async (p = 1, s = search, st = status) => {
    const params = new URLSearchParams({ page: String(p), page_size: "10" });
    if (s.trim()) params.set("search", s.trim());
    if (st) params.set("status", st);
    try {
      const data = await api<Page<AdminUserOut>>(`/admin/users?${params.toString()}`, {
        admin: true,
      });
      setItems(data.items);
      setPages(data.pages);
      setPage(data.page);
    } catch {
      /* auth-guard handles redirect */
    }
  }, [search, status]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(1), 250);
    return () => clearTimeout(t);
  }, [search, status, load]);

  const openAdd = () => {
    setForm({ ...EMPTY_FORM, expiry: toLocalInput(new Date(Date.now() + 365 * 864e5)) });
    setFormError("");
    setModalOpen(true);
  };

  const openEdit = (u: AdminUserOut) => {
    setForm({
      id: u.id,
      cpr: u.cpr,
      email: u.email,
      name: u.name,
      phone: u.phone ?? "",
      expiry: toLocalInput(u.expiry_date),
      password: "",
      rewards: u.reward_points,
    });
    setFormError("");
    setModalOpen(true);
  };

  const saveUser = async (e: FormEvent) => {
    e.preventDefault();
    setFormError("");
    const body: Record<string, unknown> = {
      cpr: form.cpr.trim(),
      email: form.email.trim(),
      name: form.name.trim(),
      phone: form.phone.trim() || null,
      expiry_date: new Date(form.expiry).toISOString(),
    };
    try {
      if (form.id) {
        await api(`/admin/users/${form.id}`, { method: "PUT", admin: true, body });
      } else {
        await api("/admin/users", {
          method: "POST",
          admin: true,
          body: { ...body, password: form.password, reward_points: Number(form.rewards || 0) },
        });
      }
      setModalOpen(false);
      await load(1);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Save failed.");
    }
  };

  const promptReward = async (u: AdminUserOut) => {
    const delta = window.prompt(`Adjust reward points for ${u.name} (e.g. +5 or -2):`, "+1");
    if (delta === null) return;
    const reason = window.prompt("Reason (required):", "");
    if (!reason) return;
    try {
      await api(`/admin/users/${u.id}/reward`, {
        method: "PUT",
        admin: true,
        body: { delta: Number(delta), reason },
      });
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Adjustment failed.");
    }
  };

  const resetPw = async (u: AdminUserOut) => {
    const pw = window.prompt(`New temporary password for ${u.name} (min 8 chars):`, "");
    if (!pw || pw.length < 8) {
      window.alert("Password must be at least 8 characters.");
      return;
    }
    try {
      await api(`/admin/users/${u.id}/reset-password`, {
        method: "POST",
        admin: true,
        body: { new_password: pw },
      });
      window.alert("Password reset — the user must change it on next login.");
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Reset failed.");
    }
  };

  const toggleActive = async (u: AdminUserOut) => {
    try {
      await api(`/admin/users/${u.id}/${u.is_active ? "deactivate" : "activate"}`, {
        method: "POST",
        admin: true,
      });
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Failed.");
    }
  };

  const set = (k: keyof UserFormState) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900">User Management</h1>
          <p className="mt-1 text-sm text-slate-500">
            Add, modify, deactivate, and adjust rewards.
          </p>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <button onClick={openAdd} className="btn-primary">+ Add user</button>
          <Link to="/admin" className="btn-secondary">Dashboard</Link>
          <Link to="/admin/transactions" className="btn-secondary">Ledger</Link>
        </div>
      </div>

      <div className="mt-6 flex gap-2 flex-wrap">
        <input
          className="input-field"
          placeholder="Search name / email / CPR…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="input-field" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="expired">Expired</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      <div className="mt-6 bg-white border border-slate-200 rounded-2xl overflow-x-auto">
        {items.length === 0 ? (
          <p className="p-4 text-sm text-slate-400">No users found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-slate-500">
                <th className="px-4 py-2">Name / CPR</th>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Expiry</th>
                <th className="px-4 py-2">Rewards</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">
                    <div className="font-medium text-slate-900">{u.name}</div>
                    <div className="text-xs text-slate-400">CPR {u.cpr}</div>
                  </td>
                  <td className="px-4 py-2">{u.email}</td>
                  <td className="px-4 py-2">{fmtDateOnly(u.expiry_date)}</td>
                  <td className="px-4 py-2 font-semibold">{u.reward_points}</td>
                  <td className="px-4 py-2">
                    {u.is_active ? (
                      new Date(u.expiry_date) > new Date() ? (
                        <span className="inline-block text-xs font-semibold rounded-full px-2.5 py-1 bg-brand-100 text-brand-700">Active</span>
                      ) : (
                        <span className="inline-block text-xs font-semibold rounded-full px-2.5 py-1 bg-amber-100 text-amber-700">Expired</span>
                      )
                    ) : (
                      <span className="inline-block text-xs font-semibold rounded-full px-2.5 py-1 bg-slate-200 text-slate-600">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    <button className="btn-secondary mr-1" onClick={() => openEdit(u)}>Edit</button>
                    <button className="btn-secondary mr-1" onClick={() => promptReward(u)}>+Reward</button>
                    <button className="btn-secondary mr-1" onClick={() => resetPw(u)}>Reset PW</button>
                    <button className="btn-secondary" onClick={() => toggleActive(u)}>
                      {u.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Pagination page={page} pages={pages} onPage={(p) => load(p)} />

      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 grid place-items-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl p-8 max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold text-slate-900">
              {form.id ? "Edit user" : "Add user"}
            </h2>
            <form onSubmit={saveUser} className="mt-6 space-y-4" noValidate>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700">CPR</label>
                  <input className="input-field" required minLength={5} maxLength={20} value={form.cpr} onChange={set("cpr")} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Name</label>
                  <input className="input-field" required minLength={2} maxLength={120} value={form.name} onChange={set("name")} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Email</label>
                  <input type="email" className="input-field" required value={form.email} onChange={set("email")} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Phone</label>
                  <input className="input-field" value={form.phone} onChange={set("phone")} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Expiry date</label>
                  <input type="datetime-local" className="input-field" required value={form.expiry} onChange={set("expiry")} />
                </div>
                {!form.id && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-slate-700">Initial password</label>
                      <input type="password" className="input-field" required minLength={8} maxLength={72} value={form.password} onChange={set("password")} />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700">Reward points</label>
                      <input type="number" min={0} className="input-field" value={form.rewards} onChange={set("rewards")} />
                    </div>
                  </>
                )}
              </div>
              {formError && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {formError}
                </div>
              )}
              <div className="flex gap-3">
                <button type="submit" className="btn-primary">Save user</button>
                <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Pagination from "../components/Pagination";
import { fmtDateOnly } from "./BusinessDetail";
import type { AdminBusinessOut, AreaOut, CategoryOut, Page } from "../types";

interface BranchRow {
  area_id: number | "";
  branch_name: string;
  address: string;
  phone: string;
}

interface BizFormState {
  id: number | null;
  name: string;
  commercial_registration: string;
  category_id: number | "";
  discount_percentage: string;
  description: string;
  expiry: string;
  is_active: boolean;
  branches: BranchRow[];
}

function toLocalInput(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const EMPTY_BRANCH: BranchRow = { area_id: "", branch_name: "", address: "", phone: "" };

function newForm(): BizFormState {
  return {
    id: null,
    name: "",
    commercial_registration: "",
    category_id: "",
    discount_percentage: "0",
    description: "",
    expiry: toLocalInput(new Date(Date.now() + 365 * 864e5)),
    is_active: true,
    branches: [],
  };
}

export default function AdminBusinesses() {
  const [items, setItems] = useState<AdminBusinessOut[]>([]);
  const [categories, setCategories] = useState<CategoryOut[]>([]);
  const [areas, setAreas] = useState<AreaOut[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<BizFormState>(newForm);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async (p = 1, s = search, st = status) => {
    const params = new URLSearchParams({ page: String(p), page_size: "10" });
    if (s.trim()) params.set("search", s.trim());
    if (st) params.set("status", st);
    try {
      const data = await api<Page<AdminBusinessOut>>(`/admin/businesses?${params.toString()}`, {
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
    api<CategoryOut[]>("/businesses/categories").then(setCategories).catch(() => {});
    api<AreaOut[]>("/businesses/areas").then(setAreas).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(1), 250);
    return () => clearTimeout(t);
  }, [search, status, load]);
  const openAdd = () => {
    setForm(newForm());
    setFormError("");
    setModalOpen(true);
  };

  const openEdit = (b: AdminBusinessOut) => {
    setForm({
      id: b.id,
      name: b.name,
      commercial_registration: b.commercial_registration,
      category_id: b.category_id,
      discount_percentage: String(b.discount_percentage),
      description: b.description ?? "",
      expiry: toLocalInput(b.expiry_date),
      is_active: b.is_active,
      branches: b.branches.map((br) => ({
        area_id: br.area_id,
        branch_name: br.branch_name ?? "",
        address: br.address ?? "",
        phone: br.phone ?? "",
      })),
    });
    setFormError("");
    setModalOpen(true);
  };

  const set = (k: keyof BizFormState) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const setBranch =
    (i: number, k: keyof BranchRow) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({
        ...f,
        branches: f.branches.map((r, j) => (j === i ? { ...r, [k]: e.target.value } : r)),
      }));

  const addBranch = () =>
    setForm((f) => ({ ...f, branches: [...f.branches, { ...EMPTY_BRANCH }] }));

  const removeBranch = (i: number) =>
    setForm((f) => ({ ...f, branches: f.branches.filter((_, j) => j !== i) }));

  const saveBusiness = async (e: FormEvent) => {
    e.preventDefault();
    setFormError("");
    const discount = Number(form.discount_percentage);
    if (form.category_id === "" || !Number.isFinite(discount) || discount < 0 || discount > 100) {
      setFormError("Choose a category and a discount between 0 and 100.");
      return;
    }
    const body = {
      name: form.name.trim(),
      commercial_registration: form.commercial_registration.trim(),
      category_id: Number(form.category_id),
      discount_percentage: discount,
      description: form.description.trim() || null,
      expiry_date: new Date(form.expiry).toISOString(),
      is_active: form.is_active,
      branches: form.branches
        .filter((br) => br.area_id !== "")
        .map((br) => ({
          area_id: Number(br.area_id),
          branch_name: br.branch_name.trim() || null,
          address: br.address.trim() || null,
          phone: br.phone.trim() || null,
        })),
    };
    setSaving(true);
    try {
      if (form.id) {
        await api(`/admin/businesses/${form.id}`, { method: "PUT", admin: true, body });
      } else {
        await api("/admin/businesses", { method: "POST", admin: true, body });
      }
      setModalOpen(false);
      await load(1);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (b: AdminBusinessOut) => {
    try {
      await api(`/admin/businesses/${b.id}`, {
        method: "PUT",
        admin: true,
        body: { is_active: !b.is_active },
      });
      await load();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Failed.");
    }
  };
  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900">Business Management</h1>
          <p className="mt-1 text-sm text-slate-500">Register, edit and manage merchant partnerships.</p>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <button onClick={openAdd} className="btn-primary">+ Register business</button>
          <Link to="/admin" className="btn-secondary">Dashboard</Link>
          <Link to="/admin/users" className="btn-secondary">Users</Link>
          <Link to="/admin/transactions" className="btn-secondary">Ledger</Link>
        </div>
      </div>

      <div className="mt-6 flex gap-2 flex-wrap">
        <input
          className="input-field"
          placeholder="Search name / CR / description…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="input-field" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      <div className="mt-6 bg-white border border-slate-200 rounded-2xl overflow-x-auto">
        {items.length === 0 ? (
          <p className="p-4 text-sm text-slate-400">No businesses found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-slate-500">
                <th className="px-4 py-2">Business</th>
                <th className="px-4 py-2">Category</th>
                <th className="px-4 py-2">Discount</th>
                <th className="px-4 py-2">Areas / branches</th>
                <th className="px-4 py-2">Expiry</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr key={b.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">
                    <div className="font-medium text-slate-900">{b.name}</div>
                    <div className="text-xs text-slate-400">CR {b.commercial_registration}</div>
                  </td>
                  <td className="px-4 py-2">{b.category_name ?? "—"}</td>
                  <td className="px-4 py-2 font-semibold text-brand-700">-{b.discount_percentage}%</td>
                  <td className="px-4 py-2 text-slate-500">
                    {b.branches.length
                      ? b.branches
                          .map((br) => br.area_name + (br.branch_name ? ` · ${br.branch_name}` : ""))
                          .join(", ")
                      : "—"}
                  </td>
                  <td className="px-4 py-2">{fmtDateOnly(b.expiry_date)}</td>
                  <td className="px-4 py-2">
                    {b.is_active ? (
                      new Date(b.expiry_date) > new Date() ? (
                        <span className="inline-block text-xs font-semibold rounded-full px-2.5 py-1 bg-brand-100 text-brand-700">Active</span>
                      ) : (
                        <span className="inline-block text-xs font-semibold rounded-full px-2.5 py-1 bg-amber-100 text-amber-700">Expired</span>
                      )
                    ) : (
                      <span className="inline-block text-xs font-semibold rounded-full px-2.5 py-1 bg-slate-200 text-slate-600">Inactive</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    <button className="btn-secondary mr-1" onClick={() => openEdit(b)}>Edit</button>
                    <button className="btn-secondary" onClick={() => toggleActive(b)}>
                      {b.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Pagination page={page} pages={pages} onPage={(p) => load(p)} />
      {/* --- Register / edit modal --- */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 grid place-items-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl p-8 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold text-slate-900">
              {form.id ? "Edit business" : "Register business"}
            </h2>
            <form onSubmit={saveBusiness} className="mt-6 space-y-4" noValidate>
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label htmlFor="biz-name" className="block text-sm font-medium text-slate-700">Business name</label>
                  <input id="biz-name" className="input-field" required minLength={2} maxLength={160} value={form.name} onChange={set("name")} />
                </div>
                <div>
                  <label htmlFor="biz-cr" className="block text-sm font-medium text-slate-700">Commercial registration</label>
                  <input id="biz-cr" className="input-field" required minLength={3} maxLength={60} value={form.commercial_registration} onChange={set("commercial_registration")} />
                </div>
                <div>
                  <label htmlFor="biz-category" className="block text-sm font-medium text-slate-700">Category</label>
                  <select id="biz-category" className="input-field" required value={form.category_id} onChange={(e) => setForm((f) => ({ ...f, category_id: Number(e.target.value) || "" }))}>
                    <option value="">Select category…</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="biz-discount" className="block text-sm font-medium text-slate-700">Discount %</label>
                  <input id="biz-discount" type="number" min={0} max={100} className="input-field" required value={form.discount_percentage} onChange={set("discount_percentage")} />
                </div>
                <div>
                  <label htmlFor="biz-expiry" className="block text-sm font-medium text-slate-700">Partnership expiry</label>
                  <input id="biz-expiry" type="datetime-local" className="input-field" required value={form.expiry} onChange={set("expiry")} />
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="biz-desc" className="block text-sm font-medium text-slate-700">Description</label>
                  <textarea id="biz-desc" rows={3} className="input-field" maxLength={2000} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
                </div>
                <div className="sm:col-span-2 flex items-center gap-2">
                  <input id="biz-active" type="checkbox" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
                  <label htmlFor="biz-active" className="text-sm font-medium text-slate-700">Active partnership</label>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-slate-900">Areas / branches</h3>
                  <button type="button" className="btn-secondary" onClick={addBranch}>+ Add branch</button>
                </div>
                <div className="mt-3 space-y-3">
                  {form.branches.length === 0 ? (
                    <p className="text-sm text-slate-400">No branches — add at least one area so volunteers know where the discount applies.</p>
                  ) : (
                    form.branches.map((br, i) => (
                      <div key={i} className="grid sm:grid-cols-[1fr_1.2fr_1.2fr_1fr_auto] gap-2 items-center border border-slate-200 rounded-xl p-3">
                        <select className="input-field" value={br.area_id} onChange={setBranch(i, "area_id")} required>
                          <option value="">Area…</option>
                          {areas.map((a) => (
                            <option key={a.id} value={a.id}>{a.name}</option>
                          ))}
                        </select>
                        <input className="input-field" placeholder="Branch name" maxLength={120} value={br.branch_name} onChange={setBranch(i, "branch_name")} />
                        <input className="input-field" placeholder="Address" maxLength={255} value={br.address} onChange={setBranch(i, "address")} />
                        <input className="input-field" placeholder="Phone" maxLength={30} value={br.phone} onChange={setBranch(i, "phone")} />
                        <button type="button" className="btn-secondary text-red-600" onClick={() => removeBranch(i)}>✕</button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {formError && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{formError}</div>
              )}
              <div className="flex gap-3">
                <button type="submit" disabled={saving} className="btn-primary">{saving ? "Saving…" : "Save business"}</button>
                <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
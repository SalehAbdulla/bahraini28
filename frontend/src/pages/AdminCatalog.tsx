import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { AdminAreaOut, CategoryOut } from "../types";

type Notice = { kind: "ok" | "err"; text: string } | null;

export default function AdminCatalog() {
  const [areas, setAreas] = useState<AdminAreaOut[]>([]);
  const [categories, setCategories] = useState<CategoryOut[]>([]);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);

  const [newArea, setNewArea] = useState("");
  const [newCategory, setNewCategory] = useState({ name: "", description: "" });
  const [areaEdit, setAreaEdit] = useState<{ id: number; name: string } | null>(null);
  const [categoryEdit, setCategoryEdit] = useState<{
    id: number;
    name: string;
    description: string;
  } | null>(null);

  const loadAreas = useCallback(() => {
    api<AdminAreaOut[]>("/admin/areas", { admin: true })
      .then(setAreas)
      .catch(() => {});
  }, []);
  const loadCategories = useCallback(() => {
    api<CategoryOut[]>("/admin/categories", { admin: true })
      .then(setCategories)
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadAreas();
    loadCategories();
  }, [loadAreas, loadCategories]);

  const run = async (fn: () => Promise<unknown>, okText: string): Promise<boolean> => {
    setBusy(true);
    setNotice(null);
    try {
      await fn();
      setNotice({ kind: "ok", text: okText });
      loadAreas();
      loadCategories();
      return true;
    } catch (e) {
      setNotice({ kind: "err", text: e instanceof Error ? e.message : "Request failed." });
      return false;
    } finally {
      setBusy(false);
    }
  };

  // --- Areas -----------------------------------------------------------------
  const addArea = async (e: FormEvent) => {
    e.preventDefault();
    const name = newArea.trim();
    if (!name) return;
    const ok = await run(
      () => api("/admin/areas", { method: "POST", admin: true, body: { name } }),
      "Area added."
    );
    if (ok) setNewArea("");
  };

  const saveArea = async () => {
    if (!areaEdit) return;
    const { id, name } = areaEdit;
    const ok = await run(
      () => api(`/admin/areas/${id}`, { method: "PUT", admin: true, body: { name: name.trim() } }),
      "Area updated."
    );
    if (ok) setAreaEdit(null);
  };

  const toggleArea = (area: AdminAreaOut) =>
    run(
      () =>
        api(`/admin/areas/${area.id}`, {
          method: "PUT",
          admin: true,
          body: { is_active: !area.is_active },
        }),
      area.is_active ? "Area deactivated." : "Area activated."
    );

  const deleteArea = (area: AdminAreaOut) =>
    run(() => api(`/admin/areas/${area.id}`, { method: "DELETE", admin: true }), "Area deleted.");

  // --- Categories ------------------------------------------------------------
  const addCategory = async (e: FormEvent) => {
    e.preventDefault();
    const name = newCategory.name.trim();
    if (!name) return;
    const ok = await run(
      () =>
        api("/admin/categories", {
          method: "POST",
          admin: true,
          body: { name, description: newCategory.description.trim() || null },
        }),
      "Category added."
    );
    if (ok) setNewCategory({ name: "", description: "" });
  };

  const saveCategory = async () => {
    if (!categoryEdit) return;
    const { id, name, description } = categoryEdit;
    const ok = await run(
      () =>
        api(`/admin/categories/${id}`, {
          method: "PUT",
          admin: true,
          body: { name: name.trim(), description: description.trim() || null },
        }),
      "Category updated."
    );
    if (ok) setCategoryEdit(null);
  };

  const deleteCategory = (category: CategoryOut) =>
    run(
      () => api(`/admin/categories/${category.id}`, { method: "DELETE", admin: true }),
      "Category deleted."
    );

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900">Areas &amp; Categories</h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage the geographic areas and merchant categories used across the directory.
          </p>
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <Link to="/admin" className="btn-secondary">
            Dashboard
          </Link>
          <Link to="/admin/businesses" className="btn-secondary">
            Businesses
          </Link>
        </div>
      </div>

      {notice && (
        <div
          className={`mt-4 rounded-lg px-4 py-2 text-sm ${
            notice.kind === "ok"
              ? "bg-brand-50 text-brand-700 border border-brand-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          {notice.text}
        </div>
      )}

      <div className="mt-8 grid lg:grid-cols-2 gap-6">
        {/* Areas */}
        <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Areas</h2>
            <span className="text-xs text-slate-400">{areas.length} total</span>
          </div>

          <form onSubmit={addArea} className="mt-4 flex gap-2">
            <input
              className="input-field"
              placeholder="Add a new area…"
              maxLength={80}
              value={newArea}
              onChange={(e) => setNewArea(e.target.value)}
            />
            <button className="btn-primary" disabled={busy || !newArea.trim()}>
              Add
            </button>
          </form>

          <ul className="mt-4 divide-y divide-slate-100">
            {areas.map((area) => (
              <li key={area.id} className="py-2 flex items-center gap-2">
                {areaEdit?.id === area.id ? (
                  <>
                    <input
                      className="input-field"
                      maxLength={80}
                      value={areaEdit.name}
                      autoFocus
                      onChange={(e) => setAreaEdit({ id: area.id, name: e.target.value })}
                    />
                    <button className="btn-primary" disabled={busy} onClick={saveArea}>
                      Save
                    </button>
                    <button className="btn-secondary" onClick={() => setAreaEdit(null)}>
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <span
                      className={`flex-1 text-sm ${
                        area.is_active ? "text-slate-800" : "text-slate-400 line-through"
                      }`}
                    >
                      {area.name}
                    </span>
                    <button
                      className="btn-secondary"
                      onClick={() => setAreaEdit({ id: area.id, name: area.name })}
                    >
                      Rename
                    </button>
                    <button
                      className="btn-secondary"
                      disabled={busy}
                      onClick={() => toggleArea(area)}
                    >
                      {area.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      className="btn-secondary text-red-600"
                      disabled={busy}
                      onClick={() => deleteArea(area)}
                    >
                      ✕
                    </button>
                  </>
                )}
              </li>
            ))}
            {areas.length === 0 && <li className="py-3 text-sm text-slate-400">No areas yet.</li>}
          </ul>
        </section>

        {/* Categories */}
        <section className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Categories</h2>
            <span className="text-xs text-slate-400">{categories.length} total</span>
          </div>

          <form onSubmit={addCategory} className="mt-4 flex flex-col sm:flex-row gap-2">
            <input
              className="input-field"
              placeholder="New category name…"
              maxLength={80}
              value={newCategory.name}
              onChange={(e) => setNewCategory({ ...newCategory, name: e.target.value })}
            />
            <input
              className="input-field"
              placeholder="Description (optional)"
              maxLength={255}
              value={newCategory.description}
              onChange={(e) => setNewCategory({ ...newCategory, description: e.target.value })}
            />
            <button className="btn-primary" disabled={busy || !newCategory.name.trim()}>
              Add
            </button>
          </form>

          <ul className="mt-4 divide-y divide-slate-100">
            {categories.map((category) => (
              <li key={category.id} className="py-2 flex items-center gap-2">
                {categoryEdit?.id === category.id ? (
                  <>
                    <input
                      className="input-field"
                      maxLength={80}
                      value={categoryEdit.name}
                      autoFocus
                      onChange={(e) => setCategoryEdit({ ...categoryEdit, name: e.target.value })}
                    />
                    <input
                      className="input-field"
                      placeholder="Description"
                      maxLength={255}
                      value={categoryEdit.description}
                      onChange={(e) =>
                        setCategoryEdit({ ...categoryEdit, description: e.target.value })
                      }
                    />
                    <button className="btn-primary" disabled={busy} onClick={saveCategory}>
                      Save
                    </button>
                    <button className="btn-secondary" onClick={() => setCategoryEdit(null)}>
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <div className="flex-1">
                      <div className="text-sm text-slate-800">{category.name}</div>
                      {category.description && (
                        <div className="text-xs text-slate-400">{category.description}</div>
                      )}
                    </div>
                    <button
                      className="btn-secondary"
                      onClick={() =>
                        setCategoryEdit({
                          id: category.id,
                          name: category.name,
                          description: category.description ?? "",
                        })
                      }
                    >
                      Edit
                    </button>
                    <button
                      className="btn-secondary text-red-600"
                      disabled={busy}
                      onClick={() => deleteCategory(category)}
                    >
                      ✕
                    </button>
                  </>
                )}
              </li>
            ))}
            {categories.length === 0 && (
              <li className="py-3 text-sm text-slate-400">No categories yet.</li>
            )}
          </ul>
        </section>

      </div>
    </>
  );
}

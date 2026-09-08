import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import BusinessCard from "../components/BusinessCard";
import Pagination from "../components/Pagination";
import type { AreaOut, BusinessSummary, CategoryOut, Page } from "../types";

export default function Directory() {
  const [items, setItems] = useState<BusinessSummary[]>([]);
  const [categories, setCategories] = useState<CategoryOut[]>([]);
  const [areas, setAreas] = useState<AreaOut[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [category, setCategory] = useState("");
  const [areaId, setAreaId] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (p = 1, cat = category, area = areaId, q = query) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), page_size: "9" });
      if (cat) params.set("category", cat);
      if (area) params.set("area_id", area);
      if (q.trim()) params.set("q", q.trim());
      const data = await api<Page<BusinessSummary>>(`/businesses?${params.toString()}`);
      setItems(data.items);
      setPages(data.pages);
      setPage(data.page);
    } finally {
      setLoading(false);
    }
  }, [category, areaId, query]);

  useEffect(() => {
    api<CategoryOut[]>("/businesses/categories").then(setCategories).catch(() => {});
    api<AreaOut[]>("/businesses/areas").then(setAreas).catch(() => {});
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(1, category, areaId, query), 300);
    return () => clearTimeout(t);
  }, [category, areaId, query, load]);

  return (
    <>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900">Partner Directory</h1>
          <p className="mt-1 text-slate-500 text-sm">
            Discounted businesses across Bahrain — filtered by category and area.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <select
            className="input-field"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>{c.name}</option>
            ))}
          </select>
          <select
            className="input-field"
            value={areaId}
            onChange={(e) => setAreaId(e.target.value)}
          >
            <option value="">All areas</option>
            {areas.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <input
            type="search"
            className="input-field"
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {loading ? (
        <p className="mt-10 text-slate-400 text-center py-16">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-10 text-slate-400 text-center py-16">
          No businesses match your filters.
        </p>
      ) : (
        <div className="mt-8 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {items.map((b) => (
            <BusinessCard key={b.id} business={b} />
          ))}
        </div>
      )}

      <Pagination page={page} pages={pages} onPage={(p) => load(p)} />
    </>
  );
}
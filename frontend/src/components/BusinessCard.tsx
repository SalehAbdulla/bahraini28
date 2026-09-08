import { Link } from "react-router-dom";
import type { BusinessSummary } from "../types";

export default function BusinessCard({ business }: { business: BusinessSummary }) {
  return (
    <Link
      to={`/businesses/${business.id}`}
      className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm hover:shadow-md transition flex flex-col gap-2"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-brand-600">
          {business.category_name ?? "Partner"}
        </span>
        <span className="inline-block text-xs font-semibold rounded-full px-2.5 py-1 bg-brand-100 text-brand-700">
          -{business.discount_percentage}%
        </span>
      </div>
      <h3 className="font-semibold text-slate-900">{business.name}</h3>
      <p className="text-xs text-slate-500">{(business.areas ?? []).join(" · ") || "—"}</p>
    </Link>
  );
}
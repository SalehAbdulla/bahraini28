import { Link } from "react-router-dom";
import type { BusinessSummary } from "../types";

export default function BusinessCard({ business }: { business: BusinessSummary }) {
  return (
    <Link
      to={`/businesses/${business.id}`}
      className="group flex h-full flex-col border border-ink-900/10 bg-white p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-card-hover"
    >
      <div className="flex items-start justify-between">
        {business.logo_url ? (
          <img
            src={business.logo_url}
            alt={business.name}
            className="h-12 w-12 rounded-lg object-contain"
          />
        ) : (
          <span className="grid h-12 w-12 place-items-center rounded-lg bg-brand-50 text-xl font-bold text-brand-700">
            {business.name.charAt(0)}
          </span>
        )}
        <span className="border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700">
          -{business.discount_percentage}%
        </span>
      </div>

      <span className="mt-5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-800/50">
        {business.category_name ?? "Partner"}
      </span>
      <h3 className="mt-2 font-serif text-lg font-normal text-ink-900">
        {business.name}
      </h3>
      <p className="mt-1.5 text-xs leading-relaxed text-ink-800/60">
        {(business.areas ?? []).join(" · ") || "—"}
      </p>

      <span className="mt-auto inline-flex items-center gap-1.5 pt-5 text-xs font-semibold text-ink-900">
        View partner
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
          aria-hidden="true"
        >
          <path d="M7 17L17 7" />
          <path d="M8 7h9v9" />
        </svg>
      </span>
    </Link>
  );
}
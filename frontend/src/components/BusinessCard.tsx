import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { BusinessSummary } from "../types";
import { benefitHeadline } from "../lib/benefit";

/**
 * The member benefit is a member-only reveal: for an anonymous visitor the API
 * withholds the discount, so the card shows a lock badge instead of a number.
 */
export default function BusinessCard({ business }: { business: BusinessSummary }) {
  const { isUser } = useAuth();
  const benefit = benefitHeadline(business);
  const locked = !isUser && !benefit;
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
        {benefit ? (
          <span className="border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700">
            {benefit}
          </span>
        ) : locked ? (
          <span className="inline-flex items-center gap-1 border border-ink-900/15 bg-ink-900/5 px-2.5 py-1 text-xs font-semibold text-ink-800/70">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-3 w-3"
              aria-hidden="true"
            >
              <rect x="5" y="11" width="14" height="9" rx="1" />
              <path d="M8 11V8a4 4 0 0 1 8 0v3" />
            </svg>
            Members only
          </span>
        ) : null}
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
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import BusinessCard from "../components/BusinessCard";
import type { BusinessSummary } from "../types";

export default function Landing() {
  const [featured, setFeatured] = useState<BusinessSummary[]>([]);

  useEffect(() => {
    api<{ items: BusinessSummary[] }>("/businesses?page_size=3")
      .then((data) => setFeatured(data.items))
      .catch(() => setFeatured([]));
  }, []);

  return (
    <>
      <section className="py-10 lg:py-16">
        <div className="max-w-3xl">
          <span className="inline-block text-xs font-semibold uppercase tracking-widest text-brand-700 bg-brand-50 border border-brand-200 rounded-full px-3 py-1 mb-4">
            Volunteer Members Only
          </span>
          <h1 className="text-4xl lg:text-5xl font-extrabold text-slate-900 leading-tight">
            Exclusive discounts for volunteers,
            <br />
            <span className="text-brand-600">tracked simply &amp; securely.</span>
          </h1>
          <p className="mt-5 text-lg text-slate-600">
            Explore discounted businesses across Bahrain, submit your
            physical-store invoices, and watch your rewards grow — all in one
            portal.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/directory" className="btn-primary">
              Browse the Directory
            </Link>
            <Link to="/login" className="btn-secondary">
              Member Login
            </Link>
          </div>
        </div>

        {featured.length > 0 && (
          <div className="mt-16">
            <h2 className="text-2xl font-bold text-slate-900 mb-4">
              Featured partners
            </h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {featured.map((b) => (
                <BusinessCard key={b.id} business={b} />
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="mt-14 grid md:grid-cols-3 gap-6">
        {[
          ["🏪", "Verified Discounts", "Physical merchant partners offering tiered discounts across Bahrain."],
          ["🎁", "Rewards Tracking", "Submit invoice numbers after your purchase and grow your rewards balance."],
          ["🔒", "Strict Membership Validation", "Expiry checks and single-session security keep the benefit exclusive."],
        ].map(([icon, title, desc]) => (
          <div key={title} className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
            <div className="text-3xl">{icon}</div>
            <h3 className="mt-3 font-semibold text-slate-900">{title}</h3>
            <p className="mt-1.5 text-sm text-slate-600">{desc}</p>
          </div>
        ))}
      </section>
    </>
  );
}
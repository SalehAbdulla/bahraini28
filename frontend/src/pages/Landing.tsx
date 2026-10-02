import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import BusinessCard from "../components/BusinessCard";
import type { BusinessSummary } from "../types";

/** The three promises of the programme (original copy, rebranded). */
const PILLARS = [
  {
    icon: "🏪",
    title: "Verified discounts",
    body: "Physical merchant partners across Bahrain offering tiered discounts to volunteer members.",
  },
  {
    icon: "🎁",
    title: "Rewards tracking",
    body: "Submit your invoice number after a purchase and watch your rewards balance grow.",
  },
  {
    icon: "🔒",
    title: "Strict membership validation",
    body: "Expiry checks and single-session security keep the benefit exclusive to volunteers.",
  },
];

const STEPS = [
  {
    step: "01",
    title: "Browse the directory",
    body: "Filter verified partners by category and area across all four governorates.",
  },
  {
    step: "02",
    title: "Shop at the store",
    body: "Show your membership at the counter — the discount is applied on the spot.",
  },
  {
    step: "03",
    title: "Submit your invoice",
    body: "Add the invoice number to the portal and your rewards balance is credited.",
  },
];

export default function Landing() {
  const [featured, setFeatured] = useState<BusinessSummary[]>([]);

  useEffect(() => {
    api<{ items: BusinessSummary[] }>("/businesses?page_size=3")
      .then((data) => setFeatured(data.items))
      .catch(() => setFeatured([]));
  }, []);

  return (
    <>
      {/*
        Hero — the dark "ink" canvas from the brand deck (pages 1, 5 and 6):
        charcoal spotlight texture, the green brush logo and the script voice.
      */}
      <section className="relative overflow-hidden rounded-3xl bg-ink-900 bg-texture-ink bg-cover bg-center text-cream-100">
        {/* Ink wash keeps the charcoal plate while the texture reads through. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-gradient-to-br from-ink-900/75 via-ink-900/60 to-ink-900/92"
        />
        {/* Dot-grid motif from the cover / closing plates of the identity deck. */}
        <div
          aria-hidden="true"
          className="dot-grid pointer-events-none absolute -right-4 -top-4 h-40 w-44 text-brand-500/30"
        />

        <div className="relative grid gap-10 px-6 py-12 sm:px-10 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:px-14 lg:py-16">
          <div className="max-w-2xl">
            <div className="flex flex-wrap items-center gap-3">
              {/* 44px slot — the 240px variant still resolves at 4× DPR. */}
              <img src="/brand/logo-sm.png" alt="Bahraini 28" className="h-11 w-auto" />
              <span className="eyebrow border border-brand-500/40 bg-brand-500/10 text-brand-300">
                Volunteer members only
              </span>
            </div>

            <p className="mt-7 font-script text-3xl leading-none text-cream-100 sm:text-4xl">
              Hello Bahrainies!
            </p>
            <h1 className="mt-3 text-3xl font-extrabold leading-tight text-white sm:text-4xl lg:text-5xl">
              Exclusive discounts for volunteers,{" "}
              <span className="text-brand-300">tracked simply &amp; securely.</span>
            </h1>
            <p className="mt-5 text-base text-cream-100/80 sm:text-lg">
              Explore discounted businesses across Bahrain, submit your physical-store
              invoices, and watch your rewards grow — all in one portal.
            </p>
            {/* The organisation's tagline, set exactly as in the brand deck. */}
            <p
              dir="rtl"
              lang="ar"
              className="mt-5 text-base leading-loose text-brand-300 sm:text-lg"
            >
              شراكة مجتمعية معطاءة.. بين شغف مواطن، ووقفة وطن!
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/directory" className="btn-cream">
                Browse the directory
              </Link>
              <Link to="/login" className="btn-ghost-light">
                Member login
              </Link>
            </div>
          </div>

          <div className="hidden lg:block">
            <img
              src="/brand/badge.png"
              alt=""
              aria-hidden="true"
              className="w-48 drop-shadow-2xl xl:w-60"
            />
          </div>
        </div>
      </section>

      {/* Pillars ------------------------------------------------------------
          White cards on the warm watercolour wash (deck pages 4 and 8).
          The texture is anchored to its clean top band so the deck's brush
          strokes (bottom-right of the source) never collide with the cards. */}
      <section className="mt-12 overflow-hidden rounded-3xl border border-cream-200 bg-cream-50 bg-texture-cream bg-cover bg-top p-6 sm:p-8">
        <div className="grid gap-6 md:grid-cols-3">
          {PILLARS.map((pillar) => (
            <article key={pillar.title} className="card p-6">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-100 text-xl">
                {pillar.icon}
              </span>
              <h2 className="mt-4 font-semibold text-ink-900">{pillar.title}</h2>
              <p className="mt-1.5 text-sm text-slate-600">{pillar.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* How the rewards work ---------------------------------------------- */}
      <section className="mt-14">
        <h2 className="text-2xl font-bold text-ink-900">How the rewards work</h2>
        <p className="mt-1 text-sm text-slate-600">
          Three steps between a purchase and a growing rewards balance.
        </p>
        <ol className="mt-6 grid gap-5 md:grid-cols-3">
          {STEPS.map((item) => (
            <li
              key={item.step}
              className="rounded-2xl border border-brand-100 bg-brand-50 p-6"
            >
              <span className="font-script text-3xl leading-none text-brand-600">
                {item.step}
              </span>
              <h3 className="mt-2 font-semibold text-ink-900">{item.title}</h3>
              <p className="mt-1.5 text-sm text-slate-600">{item.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Featured partners -------------------------------------------------- */}
      {featured.length > 0 && (
        <section className="mt-14">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-2xl font-bold text-ink-900">Featured partners</h2>
              <p className="mt-1 text-sm text-slate-600">
                A few of the businesses honouring volunteer membership today.
              </p>
            </div>
            <Link to="/directory" className="btn-secondary">
              See all partners →
            </Link>
          </div>
          <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((business) => (
              <BusinessCard key={business.id} business={business} />
            ))}
          </div>
        </section>
      )}

      {/*
        "Soon!" — lifted straight from the identity deck, set on the mint
        watercolour wash.
      */}
      <section className="relative mt-14 overflow-hidden rounded-3xl border border-brand-100 bg-texture-mint bg-cover bg-center">
        <div className="relative px-6 py-10 sm:px-10">
          <p className="font-script text-4xl leading-none text-brand-700">Soon!</p>
          <h2 className="mt-3 text-xl font-bold text-ink-900">
            More partners, more rewards
          </h2>
          <p className="mt-2 max-w-xl text-sm text-ink-800/80">
            We are onboarding new Bahraini businesses every month, and a
            mobile-friendly rewards journey is on the way.
          </p>
        </div>
        <div
          aria-hidden="true"
          className="dot-grid pointer-events-none absolute -bottom-3 right-5 h-24 w-40 text-brand-700/25"
        />
      </section>

      {/* Closing call to action -------------------------------------------- */}
      <section className="relative mt-14 overflow-hidden rounded-3xl bg-ink-900 px-6 py-12 text-center text-cream-100 sm:px-10">
        <div
          aria-hidden="true"
          className="dot-grid pointer-events-none absolute -left-4 -top-4 h-32 w-40 text-brand-500/25"
        />
        <div className="relative">
          {/* 56px slot — the 240px variant still resolves at 4× DPR. */}
          <img
            src="/brand/logo-sm.png"
            alt=""
            aria-hidden="true"
            className="mx-auto h-14 w-auto"
          />
          <h2 className="mt-5 text-2xl font-bold text-white sm:text-3xl">
            Ready to claim your discount?
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm text-cream-100/80">
            Membership is validated against your volunteer expiry date — sign in to
            see the partners available to you today.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link to="/login" className="btn-cream">
              Member login
            </Link>
            <Link to="/directory" className="btn-ghost-light">
              Browse the directory
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
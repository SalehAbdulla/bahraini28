import { useEffect, useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import BusinessCard from "../components/BusinessCard";
import GlowingLines from "../components/GlowingLines";
import Reveal from "../components/Reveal";
import type { BusinessSummary } from "../types";

/* ---------------------------------------------------------------------------
 * Inline stroke icons (lucide-style) so the landing keeps the minimal
 * editorial language of the reference design without an icon dependency.
 * --------------------------------------------------------------------------- */
type IconProps = { className?: string };

const svgProps = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

function ShieldIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg {...svgProps} className={className}>
      <path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
      <path d="M9.5 12l2 2 3.5-4" />
    </svg>
  );
}

function GiftIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg {...svgProps} className={className}>
      <path d="M3 10h18v11H3z" />
      <path d="M2 6h20v4H2z" />
      <path d="M12 6c-1-3-4-3-4 0s3 3 4 3c1-3 4-3 4 0s-3 3-4 3" />
    </svg>
  );
}

function LockIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg {...svgProps} className={className}>
      <rect x="5" y="11" width="14" height="9" rx="1" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function StoreIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg {...svgProps} className={className}>
      <path d="M4 7l1-3h14l1 3" />
      <path d="M4 7h16v2a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0V7z" />
      <path d="M6 12v8h12v-8" />
      <path d="M9 20v-5h6v5" />
    </svg>
  );
}

function BagIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg {...svgProps} className={className}>
      <path d="M6 8h12l-1 12H7L6 8z" />
      <path d="M9 8V6a3 3 0 0 1 6 0v2" />
    </svg>
  );
}

function ReceiptIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg {...svgProps} className={className}>
      <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3z" />
      <path d="M9 8h6" />
      <path d="M9 12h6" />
    </svg>
  );
}

function ArrowRightIcon({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg {...svgProps} className={className}>
      <path d="M5 12h14" />
      <path d="M13 6l6 6-6 6" />
    </svg>
  );
}

const PILLARS: { icon: ReactElement; title: string; body: string }[] = [
  {
    icon: <ShieldIcon className="h-6 w-6" />,
    title: "Verified discounts",
    body: "Physical merchant partners across Bahrain offering tiered discounts to volunteer members.",
  },
  {
    icon: <GiftIcon className="h-6 w-6" />,
    title: "Rewards tracking",
    body: "Submit your invoice number after a purchase and watch your rewards balance grow.",
  },
  {
    icon: <LockIcon className="h-6 w-6" />,
    title: "Strict membership validation",
    body: "Expiry checks and single-session security keep the benefit exclusive to volunteers.",
  },
];

const STEPS: { step: string; icon: ReactElement; title: string; body: string }[] = [
  {
    step: "01",
    icon: <StoreIcon className="h-6 w-6" />,
    title: "Browse the directory",
    body: "Filter verified partners by category and area across all four governorates.",
  },
  {
    step: "02",
    icon: <BagIcon className="h-6 w-6" />,
    title: "Shop at the store",
    body: "Show your membership at the counter — the discount is applied on the spot.",
  },
  {
    step: "03",
    icon: <ReceiptIcon className="h-6 w-6" />,
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
    <div>
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden rounded-3xl bg-ink-900 text-cream-100">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-texture-ink bg-cover bg-center opacity-60"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-br from-ink-900/80 via-ink-900/55 to-ink-900/90"
        />
        <div
          aria-hidden="true"
          className="dot-grid absolute -right-4 -top-4 h-44 w-52 text-brand-500/30"
        />

        <div className="relative px-6 py-16 sm:px-10 lg:px-14 lg:py-24">
          <Reveal className="max-w-3xl lg:pr-56 xl:pr-0">
            <span className="eyebrow border border-brand-500/40 bg-brand-500/10 text-brand-300">
              Volunteer members only
            </span>

            <p className="mt-8 font-script text-4xl leading-none text-cream-100 sm:text-5xl">
              Hello Bahrainies!
            </p>

            <h1 className="mt-4 font-serif text-4xl font-normal leading-[1.08] tracking-[-0.015em] text-white sm:text-5xl lg:text-6xl">
              Exclusive discounts for volunteers,{" "}
              <span className="text-brand-300">tracked simply &amp; securely.</span>
            </h1>

            <p className="mt-6 max-w-xl text-base leading-relaxed text-cream-100/75 sm:text-lg">
              Explore discounted businesses across Bahrain, submit your
              physical-store invoices, and watch your rewards grow — all in one
              portal.
            </p>

            {/* The organisation's tagline, set exactly as in the brand deck. */}
            <p
              dir="rtl"
              lang="ar"
              className="mt-5 max-w-xl text-right text-lg leading-loose text-brand-300 sm:text-xl"
            >
              شراكة مجتمعية معطاءة.. بين شغف مواطن، ووقفة وطن!
            </p>

            <div className="mt-9 flex flex-wrap gap-3">
              <Link
                to="/directory"
                className="group inline-flex items-center gap-2.5 bg-cream-100 px-6 py-3.5 text-sm font-semibold text-ink-900 transition-colors hover:bg-cream-200"
              >
                Browse the directory
                <ArrowRightIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center gap-2.5 border border-cream-100/30 px-6 py-3.5 text-sm font-semibold text-cream-100 transition-colors hover:bg-cream-100/10"
              >
                Member login
              </Link>
            </div>
          </Reveal>
        </div>

        {/* Decorative badge on large screens — fully inside the card so the
            rounded edge + overflow-hidden never clip it. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute bottom-[clamp(1rem,3vw,2.5rem)] right-[clamp(1rem,3vw,2.5rem)] hidden lg:block"
        >
          <img
            src="/brand/badge.png"
            alt=""
            className="aspect-square w-[clamp(120px,16vw,240px)] object-contain opacity-90 drop-shadow-2xl"
          />
        </div>
      </section>

      {/* ── Why Bahraini 28 ─────────────────────────────────────────────── */}
      <section className="py-16 sm:py-24">
        <Reveal className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-600/80">
            Why Bahraini 28
          </p>
          <h2 className="mt-3 font-serif text-3xl font-normal leading-tight tracking-[-0.015em] text-ink-900 sm:text-4xl">
            Built around the <span className="text-brand-600">volunteer</span>
          </h2>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-ink-800/70 sm:text-base">
            A community programme that rewards the people who give their time —
            with simple, secure access to partner discounts across Bahrain.
          </p>
        </Reveal>

        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {PILLARS.map(({ icon, title, body }, i) => (
            <Reveal key={title} delay={i * 90} className="h-full">
              <article className="group h-full border border-ink-900/10 bg-white p-7 transition-all duration-300 hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-card-hover">
                <div className="flex h-12 w-12 items-center justify-center border border-brand-200 bg-brand-50 text-brand-700">
                  {icon}
                </div>
                <h3 className="mt-5 font-serif text-xl font-normal text-ink-900">
                  {title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-800/70">
                  {body}
                </p>
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── How it works ────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden rounded-3xl bg-ink-900 px-6 py-16 text-cream-100 sm:px-10 lg:px-14 lg:py-24">
        <GlowingLines />
        <div className="relative">
          <Reveal className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-300/80">
              How it works
            </p>
            <h2 className="mt-3 font-serif text-3xl font-normal leading-tight tracking-[-0.015em] text-white sm:text-4xl">
              Three steps between a purchase and a reward
            </h2>
          </Reveal>

          <div className="mt-12 grid gap-px overflow-hidden border border-cream-100/15 bg-cream-100/15 sm:grid-cols-3">
            {STEPS.map(({ step, icon, title, body }, i) => (
              <Reveal key={step} delay={i * 100} className="h-full">
                <article className="flex h-full flex-col bg-ink-900 p-8">
                  <div className="flex items-center justify-between">
                    <span className="font-script text-4xl leading-none text-brand-300">
                      {step}
                    </span>
                    <span className="text-brand-300/70">{icon}</span>
                  </div>
                  <h3 className="mt-6 font-serif text-xl font-normal text-white">
                    {title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-cream-100/70">
                    {body}
                  </p>
                </article>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Featured partners ───────────────────────────────────────────── */}
      {featured.length > 0 && (
        <section className="py-16 sm:py-24">
          <Reveal className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-600/80">
                Directory
              </p>
              <h2 className="mt-3 font-serif text-3xl font-normal leading-tight tracking-[-0.015em] text-ink-900 sm:text-4xl">
                Featured partners
              </h2>
              <p className="mt-4 max-w-xl text-sm leading-relaxed text-ink-800/70">
                A few of the businesses honouring volunteer membership today.
              </p>
            </div>
            <Link
              to="/directory"
              className="group inline-flex items-center gap-2 border border-ink-900/15 px-5 py-2.5 text-sm font-semibold text-ink-900 transition-colors hover:border-ink-900/40"
            >
              See all partners
              <ArrowRightIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
          </Reveal>

          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((business, i) => (
              <Reveal key={business.id} delay={i * 80} className="h-full">
                <BusinessCard business={business} />
              </Reveal>
            ))}
          </div>
        </section>
      )}

      {/* ── Closing CTA ─────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden rounded-3xl bg-ink-900 px-6 py-16 text-center text-cream-100 sm:px-10 lg:py-24">
        <GlowingLines />
        <div
          aria-hidden="true"
          className="dot-grid absolute -left-4 -top-4 h-32 w-40 text-brand-500/25"
        />
        <Reveal className="relative mx-auto max-w-2xl">
          <img
            src="/brand/logo-sm.png"
            alt=""
            aria-hidden="true"
            className="mx-auto h-14 w-auto"
          />
          <h2 className="mt-6 font-serif text-3xl font-normal leading-tight tracking-[-0.015em] text-white sm:text-4xl">
            Ready to claim your discount?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-cream-100/70 sm:text-base">
            Membership is validated against your volunteer expiry date — sign in
            to see the partners available to you today.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link
              to="/login"
              className="group inline-flex items-center gap-2.5 bg-cream-100 px-7 py-3.5 text-sm font-semibold text-ink-900 transition-colors hover:bg-cream-200"
            >
              Member login
              <ArrowRightIcon className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
            <Link
              to="/directory"
              className="inline-flex items-center gap-2.5 border border-cream-100/30 px-7 py-3.5 text-sm font-semibold text-cream-100 transition-colors hover:bg-cream-100/10"
            >
              Browse the directory
            </Link>
          </div>
        </Reveal>
      </section>
    </div>
  );
}
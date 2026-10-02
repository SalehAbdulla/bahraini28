import type { TransactionStatus } from "../types";

/**
 * Sharp-cornered status pill for a submission's review lifecycle.
 *
 * Colours come from the existing brand/ink/red tokens — no new palette, and the
 * radius stays 0 via the shared Tailwind radius scale.
 */
const STATUS_STYLES: Record<TransactionStatus, string> = {
  approved: "border-brand-200 bg-brand-50 text-brand-700",
  pending: "border-ink-900/15 bg-ink-900/5 text-ink-800",
  rejected: "border-red-200 bg-red-50 text-red-700",
};

export default function StatusPill({ status }: { status: TransactionStatus }) {
  return (
    <span
      className={`inline-block border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${
        STATUS_STYLES[status] ?? STATUS_STYLES.pending
      }`}
    >
      {status}
    </span>
  );
}
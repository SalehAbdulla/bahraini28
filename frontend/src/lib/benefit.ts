import type { BusinessSummary } from "../types";

/**
 * The headline benefit shown for a partner.
 *
 * An explicit `discount_label` wins over the percentage: a partner whose deal is
 * not a flat rate (a hospital's "خدمات مختارة", a weekly free ice cream, …) is
 * stored with `discount_percentage = 0`, and printing "-0%" for it would be both
 * wrong and ugly. `null` means there is nothing to show yet — render no badge at
 * all rather than a zero.
 */
export function benefitHeadline(
  business: Pick<BusinessSummary, "discount_label" | "discount_percentage">,
): string | null {
  if (business.discount_label) return business.discount_label;
  return business.discount_percentage > 0 ? `-${business.discount_percentage}%` : null;
}

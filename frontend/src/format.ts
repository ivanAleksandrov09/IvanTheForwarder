import type { Money } from "./api/types";

// Display only. Storage stays integer minor units + ISO currency (see CONVENTIONS.md).
export function formatMoney(m: Money | null | undefined, locale = "bg-BG"): string {
  if (!m) return "–";
  return new Intl.NumberFormat(locale, { style: "currency", currency: m.currency }).format(m.amount_minor / 100);
}

export function formatDateTime(iso: string | null | undefined, locale = "bg-BG"): string {
  if (!iso) return "–";
  return new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Sofia" }).format(
    new Date(iso),
  );
}

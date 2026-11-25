import i18n from "@/i18n";
import type { Money } from "@/api/types";

const locale = () => (i18n.language === "ar" ? "ar-DZ" : "fr-DZ");

/** Display only. All arithmetic happens server-side in integer centimes. */
export function formatMoney(m: Money | null | undefined): string {
  if (!m) return "—";
  return new Intl.NumberFormat(locale(), { style: "currency", currency: "DZD" }).format(Number(m.amount));
}

/** Money from an exact decimal string (e.g. an alert's observed value), display only. */
export function formatDzd(value: number | string): string {
  return new Intl.NumberFormat(locale(), { style: "currency", currency: "DZD" }).format(Number(value));
}

export function formatCompactDzd(units: number): string {
  return new Intl.NumberFormat(locale(), { notation: "compact", maximumFractionDigits: 1 }).format(units);
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat(locale()).format(n);
}

export function formatPct(v: number | null | undefined, signed = false): string {
  if (v === null || v === undefined) return "—";
  return new Intl.NumberFormat(locale(), {
    style: "percent",
    maximumFractionDigits: 1,
    signDisplay: signed ? "exceptZero" : "auto",
  }).format(v);
}

/** Timestamps are merchant-local (Africa/Algiers) without offset: format as wall-clock time. */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat(locale(), { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

export function formatDate(isoDate: string): string {
  return new Intl.DateTimeFormat(locale(), { day: "2-digit", month: "short" }).format(new Date(`${isoDate}T00:00:00`));
}

export function toIsoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Weekday name from an ISO index (0 = Monday), localised. 2026-11-02 is a Monday. */
export function formatWeekday(isoWeekday: number, style: "long" | "short" = "long"): string {
  return new Intl.DateTimeFormat(locale(), { weekday: style }).format(new Date(2026, 10, 2 + isoWeekday));
}

/** A probability/rate already in [0, 1], shown with one decimal. Statistics only, never money. */
export function formatProbability(p: number): string {
  return new Intl.NumberFormat(locale(), { style: "percent", maximumFractionDigits: 1 }).format(p);
}

export function formatMonth(isoDate: string): string {
  return new Intl.DateTimeFormat(locale(), { month: "short", year: "2-digit" }).format(new Date(`${isoDate}T00:00:00`));
}

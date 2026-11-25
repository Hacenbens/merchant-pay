/** One global filter context (period + granularity) shared by every page (blueprint §11). */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { Granularity } from "@/api/types";
import { toIsoDate } from "@/lib/format";

export type Filters = { dateFrom: string; dateTo: string; granularity: Granularity };
type Ctx = Filters & { setFilters: (patch: Partial<Filters>) => void; setLastDays: (n: number) => void };

const FilterContext = createContext<Ctx | null>(null);

/** VITE_DEMO_TODAY freezes "today" for a reproducible jury demo (data ends 2026-11-20). */
export function today(): Date {
  const frozen = import.meta.env.VITE_DEMO_TODAY as string | undefined;
  return frozen ? new Date(`${frozen}T00:00:00`) : new Date();
}

function lastDays(n: number): Pick<Filters, "dateFrom" | "dateTo"> {
  const end = today();
  const start = new Date(end);
  start.setDate(end.getDate() - (n - 1));
  return { dateFrom: toIsoDate(start), dateTo: toIsoDate(end) };
}

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setState] = useState<Filters>({ ...lastDays(30), granularity: "day" });
  const value = useMemo<Ctx>(() => ({
    ...filters,
    setFilters: (patch) => setState((f) => ({ ...f, ...patch })),
    setLastDays: (n) => setState((f) => ({ ...f, ...lastDays(n), granularity: n > 60 ? "week" : "day" })),
  }), [filters]);
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useFilters(): Ctx {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useFilters must be used inside <FilterProvider>");
  return ctx;
}

export function PeriodPicker() {
  const { t } = useTranslation();
  const f = useFilters();
  const input = "rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm";
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {[7, 30, 90].map((n) => (
        <button key={n} onClick={() => f.setLastDays(n)} className="rounded-lg px-2 py-1 text-slate-600 hover:bg-slate-100">
          {t(`filters.last${n}`)}
        </button>
      ))}
      <label className="flex items-center gap-1">{t("filters.from")}
        <input type="date" className={input} value={f.dateFrom} max={f.dateTo}
          onChange={(e) => e.target.value && f.setFilters({ dateFrom: e.target.value })} />
      </label>
      <label className="flex items-center gap-1">{t("filters.to")}
        <input type="date" className={input} value={f.dateTo} min={f.dateFrom}
          onChange={(e) => e.target.value && f.setFilters({ dateTo: e.target.value })} />
      </label>
      <select aria-label={t("filters.granularity")} className={input} value={f.granularity}
        onChange={(e) => f.setFilters({ granularity: e.target.value as Granularity })}>
        {(["day", "week", "month"] as const).map((g) => <option key={g} value={g}>{t(`filters.${g}`)}</option>)}
      </select>
    </div>
  );
}

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { Change } from "@/api/types";
import { useFilters } from "@/app/filters";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatMoney, formatNumber, formatPct, toIsoDate } from "@/lib/format";
import { useCollections } from "./api";

const DAY_MS = 86_400_000;
const dayCount = (from: string, to: string) =>
  Math.round((new Date(`${to}T00:00:00`).getTime() - new Date(`${from}T00:00:00`).getTime()) / DAY_MS) + 1;

const shiftDays = (isoDate: string, days: number) => {
  const d = new Date(`${isoDate}T00:00:00`);
  d.setDate(d.getDate() + days);
  return toIsoDate(d);
};

/** Period B defaults to the like-for-like period immediately before A. */
const previousPeriod = (from: string, to: string) => {
  const bTo = shiftDays(from, -1);
  return { bFrom: shiftDays(bTo, -(dayCount(from, to) - 1)), bTo };
};

/** Status totals never net against each other: each one is shown with its own reference. */
export function CollectionsPage() {
  const { t } = useTranslation();
  const filters = useFilters();
  const [a, setA] = useState({ aFrom: filters.dateFrom, aTo: filters.dateTo });
  const [b, setB] = useState(() => previousPeriod(filters.dateFrom, filters.dateTo));
  const q = useCollections({ ...a, ...b });
  const d = q.data;
  const input = "rounded-lg border border-input px-2 py-1.5 text-sm";

  const updateA = (patch: Partial<typeof a>) => {
    const next = { ...a, ...patch };
    setA(next);
    setB(previousPeriod(next.aFrom, next.aTo));
  };

  return (
    <div className="space-y-4">
      <Card title={t("collections.title")}>
        <div className="grid gap-3 md:grid-cols-2">
          <fieldset className="rounded-lg border border-border p-3">
            <legend className="px-1 text-xs font-semibold uppercase text-primary">
              {t("collections.periodA")}
            </legend>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <label className="flex items-center gap-1">{t("filters.from")}
                <input type="date" className={input} value={a.aFrom} max={a.aTo}
                  onChange={(e) => e.target.value && updateA({ aFrom: e.target.value })} />
              </label>
              <label className="flex items-center gap-1">{t("filters.to")}
                <input type="date" className={input} value={a.aTo} min={a.aFrom}
                  onChange={(e) => e.target.value && updateA({ aTo: e.target.value })} />
              </label>
            </div>
          </fieldset>

          <fieldset className="rounded-lg border border-border p-3">
            <legend className="px-1 text-xs font-semibold uppercase text-muted-foreground">
              {t("collections.periodB")}
            </legend>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <label className="flex items-center gap-1">{t("filters.from")}
                <input type="date" className={input} value={b.bFrom} max={b.bTo}
                  onChange={(e) => e.target.value && setB((prev) => ({ ...prev, bFrom: e.target.value }))} />
              </label>
              <label className="flex items-center gap-1">{t("filters.to")}
                <input type="date" className={input} value={b.bTo} min={b.bFrom}
                  onChange={(e) => e.target.value && setB((prev) => ({ ...prev, bTo: e.target.value }))} />
              </label>
              <button className="text-xs text-primary hover:underline"
                onClick={() => setB(previousPeriod(a.aFrom, a.aTo))}>
                {t("collections.previousB")}
              </button>
            </div>
          </fieldset>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">{t("collections.rules")}</p>
        {d && (
          <p className="mt-1 text-xs text-muted-foreground/70">
            {t("collections.comparing", {
              aFrom: formatDate(d.period_a.date_from), aTo: formatDate(d.period_a.date_to),
              bFrom: formatDate(d.period_b.date_from), bTo: formatDate(d.period_b.date_to),
            })}
          </p>
        )}
      </Card>

      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> : d ? (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <KpiCard label={t("kpi.collected")} value={formatMoney(d.collected_a)}
              change={d.collected_change} help={t("kpi.collectedHelp")} />
            <KpiCard label={t("kpi.acceptedCount")} value={formatNumber(d.total_count_a)}
              change={d.total_count_change} />
            <KpiCard label={t("collections.acceptanceA")} value={formatPct(d.acceptance_rate_a.value)}
              footnote={`${t("kpi.basis", {
                num: d.acceptance_rate_a.numerator, den: d.acceptance_rate_a.denominator,
              })} · ${t("collections.bRate", { value: formatPct(d.acceptance_rate_b.value) })}`} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {d.by_status.map((row) => (
              <div key={row.status} className="rounded-xl border border-border bg-card p-4 shadow-sm">
                <div className="flex items-center justify-between gap-2">
                  <StatusBadge status={row.status} />
                  <Delta change={row.amount_change} />
                </div>
                <p className="mt-2 text-xl font-semibold tabular-nums text-foreground">
                  {formatMoney(row.amount_a)}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("collections.vsB", { amount: formatMoney(row.amount_b) })}
                </p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>{t("collections.counts", {
                    a: formatNumber(row.count_a), b: formatNumber(row.count_b),
                  })}</span>
                  <Link className="text-primary hover:underline"
                    to={`/transactions?status=${row.status}&date_from=${d.period_a.date_from}&date_to=${d.period_a.date_to}`}>
                    {t("dashboard.openLedger")}
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : <EmptyState>{t("collections.empty")}</EmptyState>}
    </div>
  );
}

function Delta({ change }: { change: Change }) {
  const { t } = useTranslation();
  if (change.kind !== "comparable") {
    return (
      <span className="text-xs text-muted-foreground">
        {t(change.kind === "new_activity" ? "kpi.newActivity" : "kpi.noActivity")}
      </span>
    );
  }
  const negative = (change.pct ?? 0) < 0;
  return (
    <span className={`text-xs font-medium tabular-nums ${negative ? "text-destructive" : "text-emerald-700 dark:text-emerald-400"}`}>
      {formatPct(change.pct, true)}
    </span>
  );
}

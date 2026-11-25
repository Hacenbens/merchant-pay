import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { CustomerBook, CustomerOverview } from "@/api/types";
import { useFilters } from "@/app/filters";
import { KpiCard } from "@/components/KpiCard";
import { Badge, Card, ErrorState, Spinner } from "@/components/ui";
import { isRtl } from "@/i18n";
import { formatDate, formatMoney, formatMonth, formatNumber, formatPct } from "@/lib/format";
import { useCustomerOverview } from "./api";
import { CustomerDrawer } from "./CustomerDrawer";
import { CustomerTable } from "./CustomerTable";
import { WinbackList } from "./WinbackList";

const TABS = ["overview", "customers", "winback"] as const;
type Tab = (typeof TABS)[number];
export const WINDOWS = [90, 180, 365] as const;

/** Customer loyalty intelligence. Pseudonymous, merchant-scoped, synthetic-fixture only. */
export function CustomersPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const tab = (TABS as readonly string[]).includes(params.get("tab") ?? "") ? params.get("tab") as Tab : "overview";
  const windowDays = Number(params.get("window") ?? 180);
  const selected = params.get("c");
  const filters = useFilters();
  const q = useCustomerOverview(windowDays, filters);

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null) next.delete(k);
      else next.set(k, v);
    }
    setParams(next, { replace: true });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex h-8 items-center rounded-lg bg-muted p-[3px] text-sm" role="tablist">
          {TABS.map((k) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => set({ tab: k })}
              className={clsx("h-full rounded-md px-3 font-medium transition-all", tab === k ? "bg-background text-foreground shadow-sm dark:bg-input/30" : "text-muted-foreground hover:text-foreground")}>
              {t(`customers.tabs.${k}`)}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          {t("customers.window")}
          <select className="rounded-lg border border-input px-2 py-1" value={windowDays}
            onChange={(e) => set({ window: e.target.value })}>
            {WINDOWS.map((w) => <option key={w} value={w}>{t("customers.days", { n: w })}</option>)}
          </select>
        </label>
      </div>

      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> : (
        <>
          <BookBanner book={q.data.book} />
          {q.data.book.availability === "available" && (
            tab === "overview" ? <Overview o={q.data} />
              : tab === "customers" ? <CustomerTable windowDays={windowDays} onOpen={(c) => set({ c })} />
                : <WinbackList windowDays={windowDays} onOpen={(c) => set({ c })} />
          )}
          <MethodCard book={q.data.book} />
        </>
      )}
      <CustomerDrawer token={selected} windowDays={windowDays} onClose={() => set({ c: null })} />
    </div>
  );
}

/** Always visible: what data this rests on, and whether it can be used at all. */
function BookBanner({ book }: { book: CustomerBook }) {
  const { t } = useTranslation();
  const c = book.coverage;
  const tone = book.availability === "available" ? "border-border bg-card" : "border-sky-500/20 bg-sky-500/10";
  return (
    <section className={clsx("rounded-xl border p-4 text-sm", tone)}>
      {book.availability !== "available" && (
        <p className="mb-2 font-medium text-sky-800 dark:text-sky-300">
          {t(`customers.availability.${book.availability}`, { n: book.rules.min_customers, have: book.eligible_customers })}
        </p>
      )}
      <p className="text-muted-foreground">
        {t("customers.basis", {
          from: formatDate(book.window.date_from), to: formatDate(book.window.date_to),
          customers: formatNumber(book.eligible_customers),
          tokenised: formatNumber(c.tokenised_in_window), accepted: formatNumber(c.accepted_in_window),
          share: formatPct(c.share.value),
        })}
      </p>
      <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge tone="warning">{t("customers.synthetic")}</Badge>
        {t("customers.privacy")}
      </p>
    </section>
  );
}

function Overview({ o }: { o: CustomerOverview }) {
  const { t } = useTranslation();
  const nv = o.new_vs_returning;
  const status = Object.fromEntries(o.statuses.map((s) => [s.status, s]));
  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={t("customers.kpi.repeatRate")} value={formatPct(o.repeat_rate.value)}
          footnote={t("customers.kpi.repeatBasis", { num: o.repeat_rate.numerator, den: o.repeat_rate.denominator })}
          help={t("customers.kpi.repeatHelp")} />
        <KpiCard label={t("customers.kpi.returning")} value={formatNumber(nv.returning.customers)}
          footnote={t("customers.kpi.inPeriod", { from: formatDate(nv.period.date_from), to: formatDate(nv.period.date_to),
            value: formatMoney(nv.returning.accepted_value) })} help={t("customers.kpi.returningHelp")} />
        <KpiCard label={t("customers.kpi.new")} value={formatNumber(nv.new.customers)}
          footnote={t("customers.kpi.newValue", { value: formatMoney(nv.new.accepted_value) })}
          help={t("customers.kpi.newHelp")} />
        <KpiCard label={t("customers.kpi.atRisk")}
          value={formatNumber((status.at_risk?.customers ?? 0) + (status.lapsed?.customers ?? 0))}
          footnote={t("customers.kpi.atRiskValue", {
            atRisk: status.at_risk?.customers ?? 0, lapsed: status.lapsed?.customers ?? 0,
            value: formatMoney(status.at_risk?.accepted_value) })}
          help={t("customers.kpi.atRiskHelp")} />
      </div>

      <Card title={t("customers.segmentsTitle")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[34rem] text-sm">
            <thead className="text-start text-xs text-muted-foreground">
              <tr>
                <th className="py-1 text-start font-medium">{t("customers.col.segment")}</th>
                <th className="py-1 text-end font-medium">{t("customers.col.customers")}</th>
                <th className="py-1 text-end font-medium">{t("customers.col.transactions")}</th>
                <th className="py-1 text-end font-medium">{t("customers.col.value")}</th>
                <th className="py-1 text-end font-medium">{t("customers.col.share")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {o.segments.map((s) => (
                  <tr key={s.segment}>
                    <td className="py-2">
                      <SegmentBadge segment={s.segment} />
                      <p className="text-xs text-muted-foreground">{t(`customers.segmentHelp.${s.segment}`, rulesVars(o.book))}</p>
                    </td>
                    <td className="py-2 text-end tabular-nums">{formatNumber(s.customers)}</td>
                    <td className="py-2 text-end tabular-nums">{formatNumber(s.transactions)}</td>
                    <td className="py-2 text-end tabular-nums">{formatMoney(s.accepted_value)}</td>
                    <td className="py-2 text-end tabular-nums text-muted-foreground">{formatPct(s.value_share.value)}</td>
                  </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{t("customers.valueNote")}</p>
      </Card>

      <Card title={t("customers.monthlyTitle")}><MonthlyChart o={o} /></Card>
    </>
  );
}

export function rulesVars(book: CustomerBook) {
  const r = book.rules;
  return { newDays: r.new_days, loyalTx: r.loyal_min_tx, loyalSpan: r.loyal_min_span_days,
    q: Math.round(r.high_value_quantile * 100) };
}

const SEGMENT_TONE = {
  new: "info", one_time: "neutral", active: "neutral", loyal: "success", at_risk: "warning", lapsed: "danger",
} as const;

export function SegmentBadge({ segment }: { segment: keyof typeof SEGMENT_TONE }) {
  const { t } = useTranslation();
  return <Badge tone={SEGMENT_TONE[segment]}>{t(`customers.segment.${segment}`)}</Badge>;
}

function MonthlyChart({ o }: { o: CustomerOverview }) {
  const { t } = useTranslation();
  const rtl = isRtl();
  const data = o.monthly.map((m) => ({
    x: formatMonth(m.month_start) + (m.complete ? "" : "*"),
    new: m.new, returning: m.returning,
  }));
  return (
    <>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
            <XAxis dataKey="x" reversed={rtl} tick={{ fontSize: 11 }} />
            <YAxis orientation={rtl ? "right" : "left"} allowDecimals={false} tick={{ fontSize: 11 }} width={36} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="returning" stackId="a" fill="var(--color-primary)" name={t("customers.returning")} />
            <Bar dataKey="new" stackId="a" fill="var(--color-chart-2)" name={t("customers.new")} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{t("customers.monthlyHelp")}</p>
    </>
  );
}

function MethodCard({ book }: { book: CustomerBook }) {
  const { t } = useTranslation();
  const r = book.rules;
  return (
    <Card title={t("customers.method.title")}>
      <ul className="list-disc space-y-1 ps-5 text-xs text-muted-foreground">
        <li>{t("customers.method.data")}</li>
        <li>{t("customers.method.rfm", { days: r.window_days })}</li>
        <li>{t("customers.method.segments", { ...rulesVars(book), version: r.segments_version })}</li>
        <li>{t("customers.method.winback", {
          version: r.winback_version, personal: r.min_personal_intervals, pooled: r.min_pooled_intervals,
          watch: r.watch_ratio, risk: r.at_risk_ratio, lapsed: r.lapsed_ratio,
          riskMin: r.at_risk_min_days, lapsedMin: r.lapsed_min_days })}</li>
        <li>{t("customers.method.limits")}</li>
      </ul>
    </Card>
  );
}

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Dashboard } from "@/api/types";
import { useFilters } from "@/app/filters";
import { axisWidth, CHART_PRIMARY, SquareDot } from "@/components/charts";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { useAlerts } from "@/features/alerts/api";
import { SeverityBadge } from "@/features/alerts/SeverityBadge";
import { isRtl } from "@/i18n";
import { formatCompactDzd, formatDate, formatMoney, formatNumber, formatPct } from "@/lib/format";
import { ActivityCard } from "./ActivityCard";
import { PulseCard } from "./PulseCard";
import { useDashboard } from "./api";

export function DashboardPage() {
  const { t } = useTranslation();
  const filters = useFilters();
  const q = useDashboard(filters);
  if (q.isPending) return <Spinner />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  const d = q.data;
  const k = d.kpis;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={t("kpi.collected")} value={formatMoney(k.gross_collected)}
          change={d.collected_change} help={t("kpi.collectedHelp")} />
        <KpiCard label={t("kpi.acceptedCount")} value={formatNumber(k.accepted_count)}
          change={d.accepted_count_change} />
        <KpiCard label={t("kpi.acceptanceRate")} value={formatPct(k.acceptance_rate.value)}
          footnote={t("kpi.basis", { num: k.acceptance_rate.numerator, den: k.acceptance_rate.denominator })} />
        <KpiCard label={t("kpi.avgTicket")} value={formatMoney(k.average_ticket)} />
      </div>

      <PulseCard />

      <Card title={t("dashboard.trend")}><TrendChart d={d} /></Card>

      <ActivityCard />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("dashboard.channels")}><ChannelMix d={d} /></Card>
        <Card title={t("dashboard.statuses")}>
          <ul className="divide-y divide-border">
            {k.by_status.map((s) => (
              <li key={s.status} className="flex items-center justify-between gap-2 py-2 text-sm">
                <StatusBadge status={s.status} />
                <span className="tabular-nums text-muted-foreground">{formatNumber(s.count)}</span>
                <span className="tabular-nums font-medium">{formatMoney(s.amount)}</span>
                <Link className="text-xs text-primary hover:underline" to={`/transactions?status=${s.status}`}>
                  {t("dashboard.openLedger")}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <AlertPanel />
    </div>
  );
}

/** Top 3 open alerts: the dashboard surfaces what needs action, the Alerts page has the rest. */
function AlertPanel() {
  const { t } = useTranslation();
  const q = useAlerts("open");
  const items = (q.data?.items ?? []).slice(0, 3);
  return (
    <Card title={t("dashboard.alerts")} action={
      <Link className="text-xs text-primary hover:underline" to="/alerts">
        {t("dashboard.seeAllAlerts")}
      </Link>
    }>
      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> :
        items.length === 0 ? <EmptyState>{t("alerts.empty")}</EmptyState> : (
          <ul className="divide-y divide-border">
            {items.map((a) => (
              <li key={a.id} className="py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <SeverityBadge severity={a.severity} />
                  <span className="text-xs text-muted-foreground">
                    {t(`alerts.rules.${a.rule_code}`, { defaultValue: a.rule_code })}
                  </span>
                </div>
                <p className="mt-1 text-muted-foreground">{a.explanation}</p>
              </li>
            ))}
          </ul>
        )}
    </Card>
  );
}

function TrendChart({ d }: { d: Dashboard }) {
  const { t } = useTranslation();
  const data = d.series.map((p) => ({ x: p.bucket_start, amount: p.accepted_amount.centimes / 100, money: p.accepted_amount }));
  const rtl = isRtl();
  const dots = data.length <= 45;  // square dots like the reference, dropped when they would crowd
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="fillCollected" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART_PRIMARY} stopOpacity={0.2} />
              <stop offset="100%" stopColor={CHART_PRIMARY} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="x" tickFormatter={formatDate} reversed={rtl} tickMargin={8} minTickGap={16} />
          <YAxis orientation={rtl ? "right" : "left"} tickFormatter={formatCompactDzd} tickMargin={8} width={axisWidth()} />
          <Tooltip
            labelFormatter={(x) => formatDate(String(x))}
            formatter={(_v, _n, item) => [formatMoney(item.payload.money), t("kpi.collected")]}
          />
          <Area dataKey="amount" type="linear" stroke={CHART_PRIMARY} strokeWidth={2} fill="url(#fillCollected)"
            dot={dots ? <SquareDot fill={CHART_PRIMARY} size={6} /> : false}
            activeDot={<SquareDot fill={CHART_PRIMARY} size={9} />} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChannelMix({ d }: { d: Dashboard }) {
  const { t } = useTranslation();
  const [measure, setMeasure] = useState<"count" | "amount">("amount");
  const rows = [...d.channels].sort((a, b) =>
    measure === "count" ? b.count - a.count : b.accepted_amount.centimes - a.accepted_amount.centimes);
  return (
    <div>
      <div className="mb-3 inline-flex h-8 items-center rounded-lg bg-muted p-[3px] text-xs" role="tablist">
        {(["amount", "count"] as const).map((m) => (
          <button key={m} role="tab" aria-selected={measure === m} onClick={() => setMeasure(m)}
            className={`h-full rounded-md px-2.5 font-medium transition-all ${measure === m ? "bg-background text-foreground shadow-sm dark:bg-input/30" : "text-muted-foreground hover:text-foreground"}`}>
            {t(m === "amount" ? "dashboard.byAmount" : "dashboard.byCount")}
          </button>
        ))}
      </div>
      <ul className="space-y-2">
        {rows.map((c) => {
          const share = measure === "count" ? c.count_share.value : c.amount_share.value;
          return (
            <li key={c.channel} className="text-sm">
              <div className="flex justify-between">
                <span>{t(`channel.${c.channel}`)}</span>
                <span className="tabular-nums text-muted-foreground">
                  {measure === "count" ? formatNumber(c.count) : formatMoney(c.accepted_amount)} · {formatPct(share)}
                </span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-muted">
                <div className="h-2 rounded-full bg-primary" style={{ width: `${(share ?? 0) * 100}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

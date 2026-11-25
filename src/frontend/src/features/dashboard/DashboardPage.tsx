import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Dashboard } from "@/api/types";
import { useFilters } from "@/app/filters";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { useAlerts } from "@/features/alerts/api";
import { SeverityBadge } from "@/features/alerts/SeverityBadge";
import { isRtl } from "@/i18n";
import { formatCompactDzd, formatDate, formatMoney, formatNumber, formatPct } from "@/lib/format";
import { ActivityCard } from "./ActivityCard";
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

      <Card title={t("dashboard.trend")}><TrendChart d={d} /></Card>

      <ActivityCard />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("dashboard.channels")}><ChannelMix d={d} /></Card>
        <Card title={t("dashboard.statuses")}>
          <ul className="divide-y divide-slate-100">
            {k.by_status.map((s) => (
              <li key={s.status} className="flex items-center justify-between gap-2 py-2 text-sm">
                <StatusBadge status={s.status} />
                <span className="tabular-nums text-slate-600">{formatNumber(s.count)}</span>
                <span className="tabular-nums font-medium">{formatMoney(s.amount)}</span>
                <Link className="text-xs text-brand-700 hover:underline" to={`/transactions?status=${s.status}`}>
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
      <Link className="text-xs text-brand-700 hover:underline" to="/alerts">
        {t("dashboard.seeAllAlerts")}
      </Link>
    }>
      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> :
        items.length === 0 ? <EmptyState>{t("alerts.empty")}</EmptyState> : (
          <ul className="divide-y divide-slate-100">
            {items.map((a) => (
              <li key={a.id} className="py-2 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <SeverityBadge severity={a.severity} />
                  <span className="text-xs text-slate-500">
                    {t(`alerts.rules.${a.rule_code}`, { defaultValue: a.rule_code })}
                  </span>
                </div>
                <p className="mt-1 text-slate-600">{a.explanation}</p>
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
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="x" tickFormatter={formatDate} reversed={rtl} tick={{ fontSize: 11 }} minTickGap={16} />
          <YAxis orientation={rtl ? "right" : "left"} tickFormatter={formatCompactDzd} tick={{ fontSize: 11 }} width={48} />
          <Tooltip
            labelFormatter={(x) => formatDate(String(x))}
            formatter={(_v, _n, item) => [formatMoney(item.payload.money), t("kpi.collected")]}
          />
          <Bar dataKey="amount" fill="#0f766e" radius={[3, 3, 0, 0]} />
        </BarChart>
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
      <div className="mb-3 inline-flex rounded-lg border border-slate-200 p-0.5 text-xs" role="tablist">
        {(["amount", "count"] as const).map((m) => (
          <button key={m} role="tab" aria-selected={measure === m} onClick={() => setMeasure(m)}
            className={`rounded-md px-2 py-1 ${measure === m ? "bg-brand-700 text-white" : "text-slate-600"}`}>
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
                <span className="tabular-nums text-slate-600">
                  {measure === "count" ? formatNumber(c.count) : formatMoney(c.accepted_amount)} · {formatPct(share)}
                </span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-brand-600" style={{ width: `${(share ?? 0) * 100}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Simulation } from "@/api/types";
import { useFilters } from "@/app/filters";
import { Button, Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatMoney, formatNumber, formatPct } from "@/lib/format";
import { useSimulation } from "./api";
import { ScenarioLab } from "./ScenarioLab";

const DEFAULTS = { volume: 15, acceptance: 0, ticket: 0 }; // percent, points, percent

export function SimulatorPage() {
  const { t } = useTranslation();
  const filters = useFilters();
  const run = useSimulation();
  const [volume, setVolume] = useState(DEFAULTS.volume);
  const [acceptance, setAcceptance] = useState(DEFAULTS.acceptance);
  const [ticket, setTicket] = useState(DEFAULTS.ticket);
  const lastPeriod = useRef("");

  const calculate = (v = volume, a = acceptance, k = ticket) =>
    run.mutate({
      baselineFrom: filters.dateFrom,
      baselineTo: filters.dateTo,
      volumeGrowth: v / 100,
      acceptanceChange: a / 100,
      ticketChange: k / 100,
    });

  // Compute the +15% default once per baseline period, so the demo opens on a result.
  useEffect(() => {
    const key = `${filters.dateFrom}|${filters.dateTo}`;
    if (lastPeriod.current === key) return;
    lastPeriod.current = key;
    run.mutate({
      baselineFrom: filters.dateFrom,
      baselineTo: filters.dateTo,
      volumeGrowth: DEFAULTS.volume / 100,
      acceptanceChange: 0,
      ticketChange: 0,
    });
  }, [filters.dateFrom, filters.dateTo, run]);

  const reset = () => {
    setVolume(DEFAULTS.volume);
    setAcceptance(DEFAULTS.acceptance);
    setTicket(DEFAULTS.ticket);
    calculate(DEFAULTS.volume, DEFAULTS.acceptance, DEFAULTS.ticket);
  };

  return (
    <div className="space-y-4">
      <Card
        title={t("simulator.title")}
        action={
          <Button variant="ghost" className="text-xs" onClick={reset}>{t("simulator.reset")}</Button>
        }
      >
        <p className="mb-4 text-sm text-slate-500">{t("simulator.intro")}</p>

        <label className="block text-sm">
          <span className="flex items-center justify-between font-medium text-slate-700">
            <span>{t("simulator.volume")}</span>
            <span className="tabular-nums text-brand-700">{formatPct(volume / 100, true)}</span>
          </span>
          <input type="range" min={-20} max={60} step={5} value={volume}
            aria-label={t("simulator.volume")}
            onChange={(e) => setVolume(Number(e.target.value))}
            className="mt-2 w-full accent-brand-700" />
        </label>

        <details className="mt-4 rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-medium text-slate-700">
            {t("simulator.advanced")}
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-sm text-slate-600">
              {t("simulator.acceptance")}
              <input type="number" min={-10} max={20} step={1} value={acceptance}
                onChange={(e) => setAcceptance(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 tabular-nums" />
            </label>
            <label className="text-sm text-slate-600">
              {t("simulator.ticket")}
              <input type="number" min={-20} max={20} step={1} value={ticket}
                onChange={(e) => setTicket(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 tabular-nums" />
            </label>
          </div>
        </details>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={() => calculate()} disabled={run.isPending}>
            {run.isPending ? t("simulator.running") : t("simulator.run")}
          </Button>
          <span className="text-xs text-slate-500">
            {t("simulator.baselineHint", {
              from: formatDate(filters.dateFrom),
              to: formatDate(filters.dateTo),
            })}
          </span>
        </div>
        {run.isError && <p className="mt-2 text-sm text-rose-700">{t("simulator.error")}</p>}
      </Card>

      {run.isPending && !run.data ? <Spinner /> : run.isError ? (
        <ErrorState onRetry={() => calculate()} />
      ) : run.data ? (
        <Result r={run.data} />
      ) : <EmptyState>{t("simulator.empty")}</EmptyState>}

      <ScenarioLab />
    </div>
  );
}

function Result({ r }: { r: Simulation }) {
  const { t } = useTranslation();
  const p = r.projection;
  const points = (v: number) => {
    const n = Math.round(v * 100);
    return `${n > 0 ? "+" : ""}${formatNumber(n)} ${t("simulator.points")}`;
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Stat label={t("simulator.projectedCount")} value={formatNumber(p.projected_count)} />
        <Stat label={t("simulator.projectedCollection")} value={formatMoney(p.projected_collection)} />
        <Stat label={t("simulator.delta")} value={formatMoney(p.delta_collection)}
          hint={formatPct(p.delta_pct, true)} />
        <Stat label={t("simulator.projectedAcceptance")} value={formatPct(p.projected_acceptance_share)} />
        <Stat label={t("simulator.projectedTicket")} value={formatMoney(p.projected_average_ticket)} />
        <Stat label={t("simulator.baselineCollection")} value={formatMoney(r.baseline.gross_collection)} />
      </div>

      <Card title={t("simulator.assumptions")}>
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          <Row label={t("simulator.baselinePeriod")}
            value={`${formatDate(r.baseline.period.date_from)} → ${formatDate(r.baseline.period.date_to)}`} />
          <Row label={t("simulator.baselineCount")} value={formatNumber(r.baseline.total_count)} />
          <Row label={t("simulator.volume")} value={formatPct(r.assumptions.volume_growth, true)} />
          <Row label={t("simulator.acceptanceShort")} value={points(r.assumptions.acceptance_change)} />
          <Row label={t("simulator.ticketShort")} value={formatPct(r.assumptions.ticket_change, true)} />
          {r.monthly_goal && <Row label={t("simulator.goal")} value={formatMoney(r.monthly_goal)} />}
          {r.goal_gap && <Row label={t("simulator.goalGap")} value={formatMoney(r.goal_gap)} />}
        </dl>
        <p className="mt-3 text-xs text-slate-500">{t("simulator.notForecast")}</p>
      </Card>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs tabular-nums text-slate-500">{hint}</p>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="tabular-nums text-slate-800">{value}</dd>
    </div>
  );
}

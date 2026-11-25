import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { DeclineEstimate, DeclineRadar, DeclineSignal, Verdict } from "@/api/types";
import { useFilters } from "@/app/filters";
import { Badge, Card, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatMoney, formatNumber, formatProbability } from "@/lib/format";
import { useDeclineRadar } from "./api";

/** Collection Opportunity Radar: where declined value is concentrated, with honest uncertainty. */
export function InsightsPage() {
  const { t } = useTranslation();
  const filters = useFilters();
  const q = useDeclineRadar(filters);
  if (q.isPending) return <Spinner />;
  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  const r = q.data;
  // shared horizontal scale for every interval bar, so channels are visually comparable
  const scaleMax = Math.min(1, Math.max(0.1, ...[r.overall, ...r.channels]
    .flatMap((s) => [s.current.upper, s.previous.upper])) * 1.1);

  return (
    <div className="space-y-4">
      <Card title={t("insights.title")}>
        <p className="text-sm text-muted-foreground">{t("insights.intro")}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          {t("insights.periods", {
            from: formatDate(r.period.date_from), to: formatDate(r.period.date_to),
            prevFrom: formatDate(r.previous_period.date_from), prevTo: formatDate(r.previous_period.date_to),
          })}
        </p>
      </Card>

      <Card title={t("insights.overall")}>
        <SignalSummary s={r.overall} radar={r} />
        <IntervalBar s={r.overall} max={scaleMax} />
      </Card>

      <Card title={t("insights.byChannel")}>
        <ul className="divide-y divide-border">
          {r.channels.map((s) => (
            <li key={s.channel} className="py-3">
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium text-foreground">{t(`channel.${s.channel}`)}</span>
                <VerdictBadge verdict={s.verdict} />
              </div>
              <SignalSummary s={s} radar={r} compact />
              <IntervalBar s={s} max={scaleMax} />
            </li>
          ))}
        </ul>
      </Card>

      <Card title={t("insights.method.title")}>
        <ul className="list-disc space-y-1 ps-5 text-xs text-muted-foreground">
          <li>{t("insights.method.model", { a: r.method.prior_alpha, b: r.method.prior_beta,
            mean: formatProbability(r.method.prior_alpha / (r.method.prior_alpha + r.method.prior_beta)) })}</li>
          <li>{t("insights.method.denominator")}</li>
          <li>{t("insights.method.interval", { mass: formatProbability(r.method.credible_mass) })}</li>
          <li>{t("insights.method.decision", { p: formatProbability(r.method.decision_probability),
            q: formatProbability(1 - r.method.decision_probability) })}</li>
          <li>{t("insights.method.minimum", { n: r.method.min_attempts })}</li>
          <li>{t("insights.method.limits")}</li>
        </ul>
      </Card>
    </div>
  );
}

const VERDICT_TONE: Record<Verdict, "warning" | "success" | "neutral" | "info"> = {
  elevated: "warning", lower: "success", no_clear_change: "neutral", insufficient_data: "info",
};

function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { t } = useTranslation();
  return <Badge tone={VERDICT_TONE[verdict]}>{t(`insights.verdict.${verdict}`)}</Badge>;
}

function SignalSummary({ s, radar, compact = false }: { s: DeclineSignal; radar: DeclineRadar; compact?: boolean }) {
  const { t } = useTranslation();
  const ledger = new URLSearchParams({ status: "declined", date_from: radar.period.date_from,
    date_to: radar.period.date_to });
  if (s.channel) ledger.append("channel", s.channel);
  return (
    <div className="space-y-1 text-sm">
      {!compact && <VerdictBadge verdict={s.verdict} />}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
        <Stat label={t("insights.declinedValue")} value={formatMoney(s.current.declined_amount)} />
        <Stat label={t("insights.observed")} value={<Observed e={s.current} />} />
        <Stat label={t("insights.estimate")} value={<Estimate e={s.current} />} />
        <Stat label={t("insights.previous")} value={<Estimate e={s.previous} />} />
      </dl>
      <p className="text-xs text-muted-foreground">
        {s.verdict === "insufficient_data"
          ? t("insights.insufficient", { n: radar.method.min_attempts,
            cur: s.current.observed.denominator, prev: s.previous.observed.denominator })
          : t("insights.probabilityHigher", { p: formatProbability(s.probability_higher) })}
        {" · "}
        <Link className="text-primary hover:underline" to={`/transactions?${ledger}`}>
          {t("insights.openDeclined", { n: s.current.observed.numerator })}
        </Link>
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular-nums text-foreground">{value}</dd>
    </div>
  );
}

function Observed({ e }: { e: DeclineEstimate }) {
  const { t } = useTranslation();
  return <>{e.observed.value === null ? "—" : formatProbability(e.observed.value)}{" "}
    <span className="text-xs text-muted-foreground">
      ({t("kpi.basis", { num: formatNumber(e.observed.numerator), den: formatNumber(e.observed.denominator) })})
    </span></>;
}

function Estimate({ e }: { e: DeclineEstimate }) {
  return <>{formatProbability(e.mean)}{" "}
    <span className="text-xs text-muted-foreground">[{formatProbability(e.lower)} – {formatProbability(e.upper)}]</span></>;
}

/** Previous (grey) vs current (amber) 90% credible intervals on one shared scale; dots = posterior means. */
function IntervalBar({ s, max }: { s: DeclineSignal; max: number }) {
  const { t } = useTranslation();
  const pos = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  const row = (e: DeclineEstimate, color: string, label: string) => (
    <div className="flex items-center gap-2">
      <span className="w-20 shrink-0 text-[11px] text-muted-foreground">{label}</span>
      <div className="relative h-3 flex-1 rounded bg-muted" aria-hidden>
        <div className={`absolute top-0.5 h-2 rounded ${color} opacity-60`}
          style={{ insetInlineStart: pos(e.lower), width: `calc(${pos(e.upper)} - ${pos(e.lower)})` }} />
        <div className={`absolute top-0 h-3 w-1 rounded ${color}`} style={{ insetInlineStart: pos(e.mean) }} />
      </div>
    </div>
  );
  return (
    <div className="mt-2 space-y-1" role="img"
      aria-label={t("insights.intervalAria", { cur: formatProbability(s.current.mean), prev: formatProbability(s.previous.mean) })}>
      {row(s.previous, "bg-muted-foreground/40", t("insights.previousShort"))}
      {row(s.current, "bg-amber-500", t("insights.currentShort"))}
      <div className="flex justify-between ps-22 text-[10px] text-muted-foreground/70">
        <span>0 %</span><span>{formatProbability(max)}</span>
      </div>
    </div>
  );
}

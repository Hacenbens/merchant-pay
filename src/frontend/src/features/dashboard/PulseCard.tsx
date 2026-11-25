import clsx from "clsx";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { Fact, PulseItem } from "@/api/types";
import { useFilters } from "@/app/filters";
import { Card, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatDzd, formatNumber, formatPct, formatProbability } from "@/lib/format";
import { usePulse } from "./api";

const TONE_DOT: Record<PulseItem["tone"], string> = {
  positive: "bg-emerald-500", negative: "bg-rose-500", neutral: "bg-slate-400", info: "bg-sky-500",
};

/** Display only: each fact arrives as an exact string and is formatted by kind, never recomputed. */
function formatFact(key: string, f: Fact, t: TFunction): string {
  if (f.value === null) return "—";
  switch (f.kind) {
    case "money": return formatDzd(f.value);
    case "count": return formatNumber(Number(f.value));
    case "ratio": return formatPct(Number(f.value), key === "change");
    case "probability": return formatProbability(Number(f.value));
    case "date": return formatDate(f.value);
    case "code":
      if (key.endsWith("verdict")) return t(`insights.verdict.${f.value}`);
      if (key.endsWith("channel")) return t(`channel.${f.value}`);
      return t(`pulse.driver.${f.value}`);
  }
}

/** Merchant Pulse: observation -> metric -> baseline -> DZD relevance -> next check. */
export function PulseCard() {
  const { t } = useTranslation();
  const filters = useFilters();
  const q = usePulse(filters);
  return (
    <Card title={t("pulse.title")}>
      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> : (
        <>
          <ul className="space-y-3">
            {q.data.items.map((item) => <PulseLine key={item.code} item={item} />)}
          </ul>
          <p className="mt-3 text-xs text-slate-500">
            {t("pulse.footer", {
              from: formatDate(q.data.period.date_from), to: formatDate(q.data.period.date_to),
              prevFrom: formatDate(q.data.previous_period.date_from), prevTo: formatDate(q.data.previous_period.date_to),
            })}
          </p>
        </>
      )}
    </Card>
  );
}

function PulseLine({ item }: { item: PulseItem }) {
  const { t } = useTranslation();
  const values = Object.fromEntries(
    Object.entries(item.facts).map(([k, f]) => [k, formatFact(k, f, t)]));
  const opts = { ...values, interpolation: { escapeValue: false } };
  const extra = item.code === "declines" && item.facts.top_channel
    ? t("pulse.body.declines_concentration", opts)
    : item.code === "goal_behind" ? t("pulse.body.goal_needed", opts) : null;
  return (
    <li className="flex gap-3 text-sm">
      <span aria-hidden className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", TONE_DOT[item.tone])} />
      <div>
        <p className="font-medium text-slate-800">{t(`pulse.title_${item.code}`)}</p>
        <p className="text-slate-600">{t(`pulse.body.${item.code}`, opts)}{extra && <> {extra}</>}</p>
        <NextCheck item={item} />
      </div>
    </li>
  );
}

function NextCheck({ item }: { item: PulseItem }) {
  const { t } = useTranslation();
  const cls = "text-xs text-brand-700 hover:underline";
  if (item.code === "goal_not_set") return <Link className={cls} to="/profile">{t("pulse.next.profile")}</Link>;
  if (!item.evidence) return null;
  return (
    <span className="flex flex-wrap gap-x-3">
      <Link className={cls} to={`/transactions?${item.evidence}`}>
        {t(item.evidence.startsWith("status=declined") ? "pulse.next.declined" : "pulse.next.accepted")}
      </Link>
      {item.code === "declines" && <Link className={cls} to="/insights">{t("pulse.next.radar")}</Link>}
    </span>
  );
}

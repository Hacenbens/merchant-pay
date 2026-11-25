import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Activity } from "@/api/types";
import { useFilters } from "@/app/filters";
import { Card, ErrorState, Spinner } from "@/components/ui";
import { isRtl } from "@/i18n";
import { formatCompactDzd, formatDate, formatMoney, formatNumber, formatWeekday } from "@/lib/format";
import { useActivity } from "./api";

/** High- and low-activity periods (module 04), from Accepted transactions in the global period. */
export function ActivityCard() {
  const { t } = useTranslation();
  const filters = useFilters();
  const q = useActivity(filters);
  return (
    <Card title={t("activity.title")}>
      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> : <Body a={q.data} />}
    </Card>
  );
}

function Body({ a }: { a: Activity }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      {a.pattern_sufficient ? (
        <p className="text-sm text-slate-700">
          {t("activity.summary", {
            peak: formatWeekday(a.peak_weekday!), quiet: formatWeekday(a.quiet_weekday!),
            hour: `${a.peak_hour}h`,
          })}
        </p>
      ) : (
        <p className="rounded-lg bg-sky-50 p-2 text-xs text-sky-800">
          {t("activity.insufficient", { n: a.min_accepted_for_pattern, days: a.min_days_for_pattern,
            have: a.accepted_count })}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-medium text-slate-500">{t("activity.byWeekday")}</h3>
          <WeekdayChart a={a} />
        </div>
        <div>
          <h3 className="mb-1 text-xs font-medium text-slate-500">{t("activity.byHour")}</h3>
          <HourChart a={a} />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <DayList title={t("activity.busiest")} days={a.busiest_days} />
        <DayList title={t("activity.quietest")} days={a.quietest_days} />
      </div>
      <p className="text-xs text-slate-500">{t("activity.help")}</p>
    </div>
  );
}

function WeekdayChart({ a }: { a: Activity }) {
  const { t } = useTranslation();
  const data = a.weekdays.map((w) => ({
    x: formatWeekday(w.weekday, "short"),
    amount: w.average_amount_per_day ? w.average_amount_per_day.centimes / 100 : 0,
    money: w.average_amount_per_day, occurrences: w.occurrences, count: w.total.accepted_count,
  }));
  const rtl = isRtl();
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="x" reversed={rtl} tick={{ fontSize: 11 }} />
          <YAxis orientation={rtl ? "right" : "left"} tickFormatter={formatCompactDzd} tick={{ fontSize: 11 }} width={48} />
          <Tooltip formatter={(_v, _n, item) => [
            `${formatMoney(item.payload.money)} · ${t("activity.perDay", { n: item.payload.occurrences, tx: item.payload.count })}`,
            t("activity.avgPerDay"),
          ]} />
          <Bar dataKey="amount" fill="#0f766e" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function HourChart({ a }: { a: Activity }) {
  const { t } = useTranslation();
  const data = a.hours.map((h) => ({ x: `${h.hour}h`, count: h.total.accepted_count, money: h.total.accepted_amount }));
  const rtl = isRtl();
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="x" reversed={rtl} tick={{ fontSize: 10 }} interval={2} />
          <YAxis orientation={rtl ? "right" : "left"} allowDecimals={false} tick={{ fontSize: 11 }} width={32} />
          <Tooltip formatter={(_v, _n, item) => [
            `${formatNumber(item.payload.count)} · ${formatMoney(item.payload.money)}`, t("kpi.acceptedCount"),
          ]} />
          <Bar dataKey="count" fill="#0d9488" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** JS getDay() is 0 = Sunday; the API uses ISO 0 = Monday. */
const isoWeekday = (isoDate: string) => (new Date(`${isoDate}T00:00:00`).getDay() + 6) % 7;

function DayList({ title, days }: { title: string; days: Activity["busiest_days"] }) {
  const { t } = useTranslation();
  return (
    <div>
      <h3 className="mb-1 text-xs font-medium text-slate-500">{title}</h3>
      <ul className="divide-y divide-slate-100 text-sm">
        {days.map((d) => (
          <li key={d.day} className="flex items-center justify-between gap-2 py-1.5">
            <Link className="text-brand-700 hover:underline"
              to={`/transactions?status=accepted&date_from=${d.day}&date_to=${d.day}`}>
              {formatWeekday(isoWeekday(d.day), "short")}{" "}
              {formatDate(d.day)}
            </Link>
            <span className="tabular-nums text-slate-600">
              {t("activity.dayTotal", { n: d.total.accepted_count })} · {formatMoney(d.total.accepted_amount)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

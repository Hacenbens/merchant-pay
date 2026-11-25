import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Channel, LabScenario, ScenarioLab as Lab, ScenarioLabIn } from "@/api/types";
import { CHANNELS } from "@/api/types";
import { useFilters } from "@/app/filters";
import { Button, Card, ErrorState, Spinner } from "@/components/ui";
import { axisWidth } from "@/components/charts";
import { isRtl } from "@/i18n";
import { formatCompactDzd, formatDate, formatMoney, formatNumber, formatPct } from "@/lib/format";
import { useScenarioLab } from "./api";

type Name = "conservative" | "base" | "ambitious";
type Row = { name: Name; volume: string; acceptance: string; ticket: string; from: Channel | ""; to: Channel | ""; share: string };

// Example assumptions (the UI says so). Base = the brief's +15 % example.
const DEFAULTS: Row[] = [
  { name: "conservative", volume: "5", acceptance: "0", ticket: "0", from: "", to: "", share: "" },
  { name: "base", volume: "15", acceptance: "0", ticket: "0", from: "", to: "", share: "" },
  { name: "ambitious", volume: "30", acceptance: "2", ticket: "5", from: "ecommerce", to: "pos", share: "20" },
];

const frac = (s: string) => (Number((s || "0").replace(",", ".")) / 100).toFixed(4);

function toBody(rows: Row[], from: string, to: string): ScenarioLabIn | null {
  const nums = rows.flatMap((r) => [r.volume, r.acceptance, r.ticket, r.share]);
  if (nums.some((n) => n.trim() !== "" && !Number.isFinite(Number(n.replace(",", "."))))) return null;
  return {
    baseline_from: from, baseline_to: to,
    scenarios: rows.map((r) => ({
      name: r.name, volume_growth: frac(r.volume), acceptance_change: frac(r.acceptance), ticket_change: frac(r.ticket),
      shifts: r.from && r.to && r.share.trim() ? [{ from_channel: r.from, to_channel: r.to, share: frac(r.share) }] : [],
    })),
  };
}

/** Scenario Lab: three editable, channel-aware scenarios with an exact bridge. Not a forecast. */
export function ScenarioLab() {
  const { t } = useTranslation();
  const filters = useFilters();
  const lab = useScenarioLab();
  const [rows, setRows] = useState<Row[]>(DEFAULTS);
  const [selected, setSelected] = useState<Name>("ambitious");
  const [invalid, setInvalid] = useState(false);
  const lastPeriod = useRef("");

  const run = (r = rows) => {
    const body = toBody(r, filters.dateFrom, filters.dateTo);
    setInvalid(body === null);
    if (body) lab.mutate(body);
  };
  useEffect(() => {  // run the example scenarios once per baseline period
    const key = `${filters.dateFrom}|${filters.dateTo}`;
    if (lastPeriod.current === key) return;
    lastPeriod.current = key;
    const body = toBody(DEFAULTS, filters.dateFrom, filters.dateTo);
    if (body) lab.mutate(body);
  }, [filters.dateFrom, filters.dateTo, lab]);

  const edit = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const input = "w-full rounded-lg border border-input px-2 py-1 text-sm tabular-nums";
  const levers: { key: "volume" | "acceptance" | "ticket"; unit: string }[] = [
    { key: "volume", unit: "%" }, { key: "acceptance", unit: t("simulator.lab.pts") }, { key: "ticket", unit: "%" },
  ];

  return (
    <Card title={t("simulator.lab.title")}>
      <p className="mb-3 text-sm text-muted-foreground">{t("simulator.lab.intro")}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <thead className="text-xs text-muted-foreground">
            <tr><th />{rows.map((r) => <th key={r.name} className="px-1 text-start font-medium">{t(`simulator.lab.scenario.${r.name}`)}</th>)}</tr>
          </thead>
          <tbody>
            {levers.map((l) => (
              <tr key={l.key}>
                <th scope="row" className="py-1 pe-2 text-start font-normal text-muted-foreground">{t(`simulator.lab.lever.${l.key}`)} ({l.unit})</th>
                {rows.map((r, i) => (
                  <td key={r.name} className="px-1 py-1">
                    <input className={input} inputMode="decimal" value={r[l.key]} aria-label={`${t(`simulator.lab.lever.${l.key}`)} ${r.name}`}
                      onChange={(e) => edit(i, { [l.key]: e.target.value })} />
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <th scope="row" className="py-1 pe-2 text-start align-top font-normal text-muted-foreground">{t("simulator.lab.lever.mix")}</th>
              {rows.map((r, i) => (
                <td key={r.name} className="space-y-1 px-1 py-1">
                  <select className={input} value={r.from} aria-label={t("simulator.lab.from")} onChange={(e) => edit(i, { from: e.target.value as Channel | "" })}>
                    <option value="">{t("simulator.lab.noShift")}</option>
                    {CHANNELS.map((c) => <option key={c} value={c}>{t(`channel.${c}`)}</option>)}
                  </select>
                  {r.from && (
                    <>
                      <select className={input} value={r.to} aria-label={t("simulator.lab.to")} onChange={(e) => edit(i, { to: e.target.value as Channel | "" })}>
                        <option value="">{t("simulator.lab.to")}</option>
                        {CHANNELS.filter((c) => c !== r.from).map((c) => <option key={c} value={c}>{t(`channel.${c}`)}</option>)}
                      </select>
                      <input className={input} inputMode="decimal" value={r.share} placeholder="%" aria-label={t("simulator.lab.share")}
                        onChange={(e) => edit(i, { share: e.target.value })} />
                    </>
                  )}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button onClick={() => run()} disabled={lab.isPending}>{t("simulator.lab.run")}</Button>
        <Button variant="ghost" onClick={() => { setRows(DEFAULTS); run(DEFAULTS); }}>{t("simulator.reset")}</Button>
        <span className="text-xs text-muted-foreground">{t("simulator.lab.examples")}</span>
      </div>
      {invalid && <p role="alert" className="mt-2 text-sm text-destructive">{t("simulator.lab.invalid")}</p>}
      {lab.isError && <p role="alert" className="mt-2 text-sm text-destructive">{t("simulator.lab.error", { detail: lab.error.message })}</p>}

      <div className="mt-4">
        {lab.isPending && !lab.data ? <Spinner /> : lab.isError && !lab.data ? <ErrorState onRetry={() => run()} /> :
          lab.data ? <Results lab={lab.data} selected={selected} onSelect={setSelected} /> : null}
      </div>
    </Card>
  );
}

function Results({ lab, selected, onSelect }: { lab: Lab; selected: Name; onSelect: (n: Name) => void }) {
  const { t } = useTranslation();
  const b = lab.baseline;
  const s = lab.scenarios.find((x) => x.name === selected) ?? lab.scenarios[0];
  const cell = "py-1.5 text-end tabular-nums";
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">{t("simulator.lab.baseline", {
        from: formatDate(b.period.date_from), to: formatDate(b.period.date_to), collection: formatMoney(b.collection),
        tx: formatNumber(b.initiated), declined: formatMoney(b.declined_amount) })}</p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <thead className="text-xs text-muted-foreground">
            <tr>
              <th />
              <th className="text-end font-medium">{t("simulator.lab.current")}</th>
              {lab.scenarios.map((x) => (
                <th key={x.name} className="text-end font-medium">
                  <button className={clsx("rounded px-1", x.name === s.name ? "bg-primary text-primary-foreground" : "text-primary hover:underline")}
                    onClick={() => onSelect(x.name as Name)} aria-pressed={x.name === s.name}>
                    {t(`simulator.lab.scenario.${x.name}`)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            <tr><th scope="row" className="py-1.5 text-start font-normal text-muted-foreground">{t("simulator.lab.collection")}</th>
              <td className={cell}>{formatMoney(b.collection)}</td>
              {lab.scenarios.map((x) => <td key={x.name} className={clsx(cell, "font-medium")}>{formatMoney(x.collection)}</td>)}</tr>
            <tr><th scope="row" className="py-1.5 text-start font-normal text-muted-foreground">{t("simulator.lab.delta")}</th>
              <td className={cell}>—</td>
              {lab.scenarios.map((x) => <td key={x.name} className={cell}>{formatMoney(x.delta)} <span className="text-xs text-muted-foreground">{formatPct(x.delta_pct, true)}</span></td>)}</tr>
            <tr><th scope="row" className="py-1.5 text-start font-normal text-muted-foreground">{t("simulator.lab.transactions")}</th>
              <td className={cell}>{formatNumber(b.initiated)}</td>
              {lab.scenarios.map((x) => <td key={x.name} className={cell}>{formatNumber(x.transactions)}</td>)}</tr>
            <tr><th scope="row" className="py-1.5 text-start font-normal text-muted-foreground">{t("simulator.lab.declined")}
              <span className="block text-[11px] text-muted-foreground/70">{t("simulator.lab.declinedNote")}</span></th>
              <td className={cell}>{formatMoney(b.declined_amount)}</td>
              {lab.scenarios.map((x) => <td key={x.name} className={cell}>{formatMoney(x.declined_value)}</td>)}</tr>
            {lab.goal_for_period && (
              <tr><th scope="row" className="py-1.5 text-start font-normal text-muted-foreground">{t("simulator.lab.goalNeed")}
                <span className="block text-[11px] text-muted-foreground/70">{t("simulator.lab.goalNote", {
                  goal: formatMoney(lab.monthly_goal), period: formatMoney(lab.goal_for_period) })}</span></th>
                <td className={cell}>—</td>
                {lab.scenarios.map((x) => <td key={x.name} className={cell}>
                  {x.required_volume_growth === null ? "—" : x.required_volume_growth <= 0
                    ? t("simulator.lab.goalMet") : formatPct(x.required_volume_growth, true)}</td>)}</tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-medium text-muted-foreground">{t("simulator.lab.bridgeTitle", { name: t(`simulator.lab.scenario.${s.name}`) })}</h3>
          <Bridge lab={lab} s={s} />
          <p className="mt-1 text-xs text-muted-foreground">{t("simulator.lab.bridgeNote")}</p>
          {s.acceptance_capped.length > 0 && <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">{t("simulator.lab.capped", {
            channels: s.acceptance_capped.map((c) => t(`channel.${c}`)).join(", ") })}</p>}
        </div>
        <div className="overflow-x-auto">
          <h3 className="mb-1 text-xs font-medium text-muted-foreground">{t("simulator.lab.byChannel")}</h3>
          <table className="w-full text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th className="text-start font-medium">{t("tx.channel")}</th>
                <th className="text-end font-medium">{t("simulator.lab.volume")}</th>
                <th className="text-end font-medium">{t("simulator.lab.acceptance")}</th>
                <th className="text-end font-medium">{t("simulator.lab.ticket")}</th>
                <th className="text-end font-medium">{t("simulator.lab.collection")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {s.channels.map((c) => {
                const base = b.channels.find((x) => x.channel === c.channel);
                return (
                  <tr key={c.channel}>
                    <td className="py-1">{t(`channel.${c.channel}`)}</td>
                    <td className="py-1 text-end tabular-nums">{formatNumber(Math.round(c.volume * 10) / 10)}
                      <span className="block text-muted-foreground/70">{base ? formatNumber(base.initiated) : "—"}</span></td>
                    <td className="py-1 text-end tabular-nums">{formatPct(c.acceptance_share)}
                      <span className="block text-muted-foreground/70">{base ? formatPct(base.acceptance_share) : "—"}</span></td>
                    <td className="py-1 text-end tabular-nums">{formatMoney(c.average_ticket)}
                      <span className="block text-muted-foreground/70">{base?.average_ticket ? formatMoney(base.average_ticket) : "—"}</span></td>
                    <td className="py-1 text-end tabular-nums">{formatMoney(c.collection)}
                      <span className="block text-muted-foreground/70">{base ? formatMoney(base.accepted_amount) : "—"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-1 text-[11px] text-muted-foreground/70">{t("simulator.lab.channelNote")}</p>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{t("simulator.notForecast")}</p>
    </div>
  );
}

/** Waterfall: invisible base + coloured step. Geometry only; every label comes from the API values. */
function Bridge({ lab, s }: { lab: Lab; s: LabScenario }) {
  const { t } = useTranslation();
  const rtl = isRtl();
  let running = lab.baseline.collection.centimes / 100;
  const data = [{ x: t("simulator.lab.current"), base: 0, value: running, money: lab.baseline.collection, kind: "total" }];
  for (const step of s.bridge) {
    const v = step.amount.centimes / 100;
    data.push({ x: t(`simulator.lab.step.${step.step}`), base: v >= 0 ? running : running + v, value: Math.abs(v),
      money: step.amount, kind: v >= 0 ? "up" : "down" });
    running += v;
  }
  data.push({ x: t(`simulator.lab.scenario.${s.name}`), base: 0, value: running, money: s.collection, kind: "total" });
  const color = { total: "var(--color-primary)", up: "oklch(0.696 0.17 162.48)", down: "var(--color-destructive)" } as const;
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
          <XAxis dataKey="x" reversed={rtl} tick={{ fontSize: 10 }} interval={0} />
          <YAxis orientation={rtl ? "right" : "left"} tickFormatter={formatCompactDzd} tick={{ fontSize: 11 }} width={axisWidth()} />
          <Tooltip formatter={(_v, name, item) => (name === "base" ? [null, null] : [formatMoney(item.payload.money), item.payload.x])} />
          <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
          <Bar dataKey="value" stackId="w" isAnimationActive={false}>
            {data.map((d, i) => <Cell key={i} fill={color[d.kind as keyof typeof color]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

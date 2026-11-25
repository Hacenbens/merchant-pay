import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { LoyaltyRulesIn, LoyaltySimulation, LoyaltySimulationIn } from "@/api/types";
import { today } from "@/app/filters";
import { Badge, Button, Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { useMe } from "@/features/auth/api";
import { parseDzdToCentimes } from "@/features/merchant/ProfilePage";
import { formatDate, formatMoney, formatNumber, formatPct, toIsoDate } from "@/lib/format";
import { useAccrue, useLedger, useLoyaltyProgram, useLoyaltySimulation, useSaveProgram } from "./api";

type Form = {
  points: string; pointValue: string; minSpend: string; cap: string; expiry: string; budget: string;
  margin: string; fixedCost: string; window: string;
  scenarios: { name: "low" | "base" | "high"; uplift: string; redemption: string }[];
};

// Example assumptions only: the UI says so and the merchant is expected to replace them.
const DEFAULTS: Form = {
  points: "1", pointValue: "1", minSpend: "500", cap: "", expiry: "180", budget: "", margin: "", fixedCost: "0",
  window: "90",
  scenarios: [
    { name: "low", uplift: "0", redemption: "30" },
    { name: "base", uplift: "3", redemption: "50" },
    { name: "high", uplift: "6", redemption: "70" },
  ],
};

const pct = (s: string) => (Number(s.replace(",", ".")) / 100).toFixed(4);
const int = (s: string) => (s.trim() === "" ? null : Number(s));

/** Returns API-ready payload pieces, or an error key. Money goes to centimes exactly (string parse). */
function toPayload(f: Form): { rules: LoyaltyRulesIn; sim: LoyaltySimulationIn } | { error: string } {
  const pointValue = parseDzdToCentimes(f.pointValue);
  const minSpend = parseDzdToCentimes(f.minSpend);
  const budget = parseDzdToCentimes(f.budget);
  const fixed = parseDzdToCentimes(f.fixedCost);
  if (typeof pointValue !== "number" || pointValue <= 0) return { error: "pointValue" };
  if (minSpend === "invalid" || budget === "invalid" || fixed === "invalid") return { error: "amount" };
  const nums = [f.points, f.margin, ...f.scenarios.flatMap((s) => [s.uplift, s.redemption])];
  if (nums.some((n) => n.trim() !== "" && !Number.isFinite(Number(n.replace(",", "."))))) return { error: "number" };
  const rules: LoyaltyRulesIn = {
    points_per_100_dzd: Number(f.points), point_value_centimes: pointValue,
    min_eligible_spend_centimes: minSpend ?? 0, cap_points_per_customer: int(f.cap), expiry_days: int(f.expiry),
    campaign_budget_centimes: budget,
  };
  return {
    rules,
    sim: {
      rules, window_days: Number(f.window), campaign_cost_centimes: fixed ?? 0,
      gross_margin: f.margin.trim() === "" ? null : pct(f.margin),
      scenarios: f.scenarios.map((s) => ({ name: s.name, uplift: pct(s.uplift), redemption_rate: pct(s.redemption) })),
    },
  };
}

/** Rewards Studio: hypothetical programme rules, cost/break-even scenarios, and a pilot points ledger. */
export function LoyaltyPage() {
  const { t } = useTranslation();
  const me = useMe();
  const program = useLoyaltyProgram();
  const sim = useLoyaltySimulation();
  const save = useSaveProgram();
  const [form, setForm] = useState<Form>(DEFAULTS);
  const [formError, setFormError] = useState<string | null>(null);
  const initialised = useRef(false);
  const isOwner = me.data?.role === "owner";

  // Start from the saved programme's rules if one exists, then run the default scenarios once.
  useEffect(() => {
    if (initialised.current || program.isPending) return;
    initialised.current = true;
    const r = program.data?.program?.rules;
    const next = r ? {
      ...DEFAULTS, points: String(r.points_per_100_dzd), pointValue: r.point_value.amount,
      minSpend: r.min_eligible_spend.amount, cap: r.cap_points_per_customer ? String(r.cap_points_per_customer) : "",
      expiry: r.expiry_days ? String(r.expiry_days) : "", budget: r.campaign_budget?.amount ?? "",
    } : DEFAULTS;
    setForm(next);
    const p = toPayload(next);
    if ("sim" in p) sim.mutate(p.sim);
  }, [program.isPending, program.data, sim]);

  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }));
  const run = () => {
    const p = toPayload(form);
    if ("error" in p) return setFormError(p.error);
    setFormError(null);
    sim.mutate(p.sim);
  };
  const saveProgram = () => {
    const p = toPayload(form);
    if ("error" in p) return setFormError(p.error);
    setFormError(null);
    const from = today();
    from.setDate(from.getDate() - Number(form.window) + 1);  // pilot replays the same window as the simulation
    save.mutate({ rules: p.rules, effective_from: toIsoDate(from) });
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-700">{t("loyalty.title")}</h2>
          <Badge tone="warning">{t("loyalty.hypothetical")}</Badge>
        </div>
        <p className="mt-1 text-sm text-slate-600">{t("loyalty.intro")}</p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        <Card title={t("loyalty.rules.title")}>
          <div className="space-y-3 text-sm">
            <Field label={t("loyalty.rules.points")}><Input value={form.points} onChange={(v) => set({ points: v })} /></Field>
            <Field label={t("loyalty.rules.pointValue")}><Input value={form.pointValue} onChange={(v) => set({ pointValue: v })} /></Field>
            <Field label={t("loyalty.rules.minSpend")}><Input value={form.minSpend} onChange={(v) => set({ minSpend: v })} /></Field>
            <Field label={t("loyalty.rules.cap")} hint={t("loyalty.optional")}><Input value={form.cap} onChange={(v) => set({ cap: v })} /></Field>
            <Field label={t("loyalty.rules.expiry")} hint={t("loyalty.optional")}><Input value={form.expiry} onChange={(v) => set({ expiry: v })} /></Field>
            <Field label={t("loyalty.rules.budget")} hint={t("loyalty.optional")}><Input value={form.budget} onChange={(v) => set({ budget: v })} /></Field>
            <hr className="border-slate-100" />
            <p className="text-xs font-medium text-slate-500">{t("loyalty.assumptions.title")}</p>
            <Field label={t("loyalty.assumptions.margin")} hint={t("loyalty.assumptions.marginHint")}>
              <Input value={form.margin} onChange={(v) => set({ margin: v })} placeholder="25" />
            </Field>
            <Field label={t("loyalty.assumptions.fixedCost")}><Input value={form.fixedCost} onChange={(v) => set({ fixedCost: v })} /></Field>
            <Field label={t("loyalty.assumptions.window")}>
              <select className="w-full rounded-lg border border-slate-300 px-2 py-1.5" value={form.window}
                onChange={(e) => set({ window: e.target.value })}>
                {["30", "90", "180"].map((d) => <option key={d} value={d}>{t("customers.days", { n: d })}</option>)}
              </select>
            </Field>
            <table className="w-full text-xs">
              <thead className="text-slate-500">
                <tr><th className="text-start font-medium" />
                  <th className="text-start font-medium">{t("loyalty.assumptions.uplift")}</th>
                  <th className="text-start font-medium">{t("loyalty.assumptions.redemption")}</th></tr>
              </thead>
              <tbody>
                {form.scenarios.map((s, i) => (
                  <tr key={s.name}>
                    <td className="py-1 pe-2 font-medium">{t(`loyalty.scenario.${s.name}`)}</td>
                    {(["uplift", "redemption"] as const).map((k) => (
                      <td key={k} className="py-1 pe-2">
                        <Input value={s[k]} suffix="%" onChange={(v) => set({
                          scenarios: form.scenarios.map((x, j) => (j === i ? { ...x, [k]: v } : x)) })} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-slate-500">{t("loyalty.assumptions.examples")}</p>
            {formError && <p role="alert" className="text-xs text-rose-700">{t(`loyalty.errors.${formError}`)}</p>}
            {sim.isError && <p role="alert" className="text-xs text-rose-700">{t("loyalty.errors.server")}</p>}
            <div className="flex flex-wrap gap-2">
              <Button onClick={run} disabled={sim.isPending}>{t("loyalty.simulate")}</Button>
              {isOwner && (
                <Button variant="outline" onClick={saveProgram} disabled={save.isPending}>{t("loyalty.saveProgram")}</Button>
              )}
            </div>
            {save.isSuccess && <p role="status" className="text-xs text-emerald-700">
              {t("loyalty.saved", { v: save.data.version, from: formatDate(save.data.effective_from) })}</p>}
            {save.isError && <p role="alert" className="text-xs text-rose-700">{t("loyalty.errors.server")}</p>}
            {!isOwner && <p className="text-xs text-slate-500">{t("loyalty.ownerOnly")}</p>}
          </div>
        </Card>

        <div className="space-y-4">
          {sim.isPending && !sim.data ? <Spinner /> : sim.data ? <Results r={sim.data} /> : null}
          <PilotLedger isOwner={isOwner} />
        </div>
      </div>
    </div>
  );
}

function Results({ r }: { r: LoyaltySimulation }) {
  const { t } = useTranslation();
  const b = r.baseline;
  if (b.customers === 0) {
    return <Card><EmptyState>{t("loyalty.unavailable")}</EmptyState></Card>;
  }
  const row = (label: string, render: (i: number) => ReactNode, note?: string) => (
    <tr>
      <th scope="row" className="py-1.5 pe-3 text-start font-normal text-slate-600">
        {label}{note && <span className="block text-[11px] text-slate-400">{note}</span>}
      </th>
      {r.results.map((_, i) => <td key={i} className="py-1.5 text-end tabular-nums">{render(i)}</td>)}
    </tr>
  );
  const x = r.results;
  return (
    <Card title={t("loyalty.results.title")}>
      <p className="mb-3 text-xs text-slate-500">
        {t("loyalty.results.baseline", {
          from: formatDate(b.window.date_from), to: formatDate(b.window.date_to), sales: formatMoney(b.tokenised_sales),
          tx: formatNumber(b.tokenised_transactions), customers: formatNumber(b.customers),
          rate: formatPct(r.rules.reward_rate),
        })}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[30rem] text-sm">
          <thead className="text-xs text-slate-500">
            <tr><th />{x.map((s) => (
              <th key={s.name} className="text-end font-medium">
                {t(`loyalty.scenario.${s.name}`)}
                <span className="block font-normal">{t("loyalty.results.assumed", { u: formatPct(s.uplift), r: formatPct(s.redemption_rate) })}</span>
              </th>))}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {row(t("loyalty.results.incrementalSales"), (i) => formatMoney(x[i].incremental_sales), t("loyalty.results.incrementalNote"))}
            {row(t("loyalty.results.points"), (i) => formatNumber(x[i].points_issued))}
            {row(t("loyalty.results.liability"), (i) => formatMoney(x[i].reward_liability), t("loyalty.results.liabilityNote"))}
            {row(t("loyalty.results.rewardCost"), (i) => formatMoney(x[i].reward_cost))}
            {row(t("loyalty.results.existing"), (i) => formatMoney(x[i].reward_cost_on_existing_sales), t("loyalty.results.existingNote"))}
            {row(t("loyalty.results.fixedCost"), (i) => formatMoney(x[i].campaign_cost))}
            {row(t("loyalty.results.totalCost"), (i) => <span className="font-medium">{formatMoney(x[i].total_cost)}</span>)}
            {row(t("loyalty.results.gross"), (i) => x[i].gross_contribution ? formatMoney(x[i].gross_contribution) : "—")}
            {row(t("loyalty.results.net"), (i) => {
              const n = x[i].net_contribution;
              if (!n) return "—";
              return <span className={n.centimes < 0 ? "font-semibold text-rose-700" : "font-semibold text-emerald-700"}>{formatMoney(n)}</span>;
            }, t("loyalty.results.netNote"))}
            {row(t("loyalty.results.breakEven"), (i) => {
              const be = r.break_even[i];
              if (be.uplift === null) return <span className="text-xs text-slate-500">{t(`loyalty.results.be_${be.reason}`)}</span>;
              return <>{formatPct(be.uplift)}<span className="block text-[11px] text-slate-500">
                {t("loyalty.results.beDetail", { sales: formatMoney(be.incremental_sales), tx: be.incremental_transactions ?? "—" })}</span></>;
            }, t("loyalty.results.breakEvenNote"))}
            {x.some((s) => s.budget_exceeded_by) && row(t("loyalty.results.overBudget"), (i) =>
              x[i].budget_exceeded_by ? <span className="text-rose-700">{formatMoney(x[i].budget_exceeded_by)}</span> : "—")}
          </tbody>
        </table>
      </div>
      <ul className="mt-3 list-disc space-y-1 ps-5 text-xs text-slate-500">
        <li>{t("loyalty.method.equations")}</li>
        <li>{t("loyalty.method.notForecast")}</li>
        {r.gross_margin === null && <li>{t("loyalty.method.noMargin")}</li>}
      </ul>
    </Card>
  );
}

function PilotLedger({ isOwner }: { isOwner: boolean }) {
  const { t } = useTranslation();
  const q = useLedger();
  const accrue = useAccrue();
  return (
    <Card title={t("loyalty.ledger.title")} action={isOwner && q.data?.program ? (
      <Button variant="outline" className="text-xs" disabled={accrue.isPending} onClick={() => accrue.mutate()}>
        {t("loyalty.ledger.accrue")}
      </Button>) : undefined}>
      <p className="mb-2 text-xs text-slate-500">{t("loyalty.ledger.intro")}</p>
      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> :
        !q.data.program ? <EmptyState>{t("loyalty.ledger.noProgram")}</EmptyState> : (
          <>
            {accrue.data && <p role="status" className="mb-2 text-xs text-emerald-700">{t("loyalty.ledger.accrued", {
              earn: accrue.data.created_earn, expire: accrue.data.created_expire, existing: accrue.data.already_recorded })}</p>}
            {q.data.summary && (
              <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <Stat label={t("loyalty.ledger.version")} value={`v${q.data.program.version} · ${formatDate(q.data.program.effective_from)}`} />
                <Stat label={t("loyalty.ledger.earned")} value={formatNumber(q.data.summary.earned)} />
                <Stat label={t("loyalty.ledger.expired")} value={formatNumber(q.data.summary.expired)} />
                <Stat label={t("loyalty.ledger.liability")} value={formatMoney(q.data.summary.liability)} />
              </dl>
            )}
            {q.data.summary?.liability_over_budget && (
              <p className="mt-2 text-xs text-rose-700">{t("loyalty.ledger.overBudget", { over: formatMoney(q.data.summary.liability_over_budget) })}</p>
            )}
            {q.data.entries.length === 0 ? <p className="mt-2 text-xs text-slate-500">{t("loyalty.ledger.empty")}</p> : (
              <ul className="mt-3 divide-y divide-slate-100 text-xs">
                {q.data.entries.map((e) => (
                  <li key={`${e.kind}-${e.source_transaction_id}`} className="flex justify-between gap-2 py-1">
                    <span className="font-mono">{e.customer}</span>
                    <span>{t(`loyalty.ledger.kind.${e.kind}`)} · {formatDate(e.occurred_on)}</span>
                    <span className={e.points < 0 ? "tabular-nums text-rose-700" : "tabular-nums"}>{e.points > 0 ? "+" : ""}{e.points}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-slate-500">{t("loyalty.ledger.rules")}</p>
          </>
        )}
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return <div><dt className="text-xs text-slate-500">{label}</dt><dd className="tabular-nums">{value}</dd></div>;
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-700">{label}
        {hint && <span className="ms-1 font-normal text-slate-400">({hint})</span>}</span>
      {children}
    </label>
  );
}

function Input({ value, onChange, placeholder, suffix }: {
  value: string; onChange: (v: string) => void; placeholder?: string; suffix?: string;
}) {
  return (
    <span className="flex items-center gap-1">
      <input className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm focus:border-brand-600 focus:outline-none"
        inputMode="decimal" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
      {suffix && <span className="text-slate-500">{suffix}</span>}
    </span>
  );
}

import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import type { Me, MerchantPatch } from "@/api/types";
import { Button, Card, ErrorState, Spinner } from "@/components/ui";
import { useMe, useUpdateProfile } from "@/features/auth/api";
import { formatMoney, formatWeekday } from "@/lib/format";

const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;
type Day = (typeof DAYS)[number];
const ISO_WEEKDAY: Record<Day, number> = { mon: 0, tue: 1, wed: 2, thu: 3, fri: 4, sat: 5, sun: 6 };
const CATEGORY_SUGGESTIONS = ["Épicerie", "Restauration", "Pharmacie", "Habillement", "Électronique", "Services"];

/** "1 500 000,50" or "1500000.5" -> 150000050 centimes, exactly (no float). null if empty/invalid. */
export function parseDzdToCentimes(raw: string): number | null | "invalid" {
  const s = raw.replace(/[\s  ]/g, "").replace(",", ".");
  if (s === "") return null;
  const m = /^(\d{1,12})(?:\.(\d{1,2}))?$/.exec(s);
  if (!m) return "invalid";
  return Number(m[1]) * 100 + Number((m[2] ?? "").padEnd(2, "0"));
}

export function ProfilePage() {
  const me = useMe();
  if (me.isPending) return <Spinner />;
  if (me.isError) return <ErrorState onRetry={() => me.refetch()} />;
  // key: re-initialise the form if the active merchant changes
  return <ProfileForm key={me.data.merchant.merchant_id} me={me.data} />;
}

function ProfileForm({ me }: { me: Me }) {
  const { t } = useTranslation();
  const m = me.merchant;
  const save = useUpdateProfile();
  const readOnly = me.role !== "owner";
  const [name, setName] = useState(m.display_name);
  const [category, setCategory] = useState(m.category);
  const [days, setDays] = useState<Set<string>>(new Set(m.operating_days));
  const [goal, setGoal] = useState(m.monthly_goal ? m.monthly_goal.amount : "");
  const [formError, setFormError] = useState<string | null>(null);

  const toggle = (d: Day) => setDays((prev) => {
    const next = new Set(prev);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    return next;
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const centimes = parseDzdToCentimes(goal);
    if (!name.trim()) return setFormError(t("profile.errors.name"));
    if (days.size === 0) return setFormError(t("profile.errors.days"));
    if (centimes === "invalid" || centimes === 0) return setFormError(t("profile.errors.goal"));
    const body: MerchantPatch = {
      display_name: name.trim(),
      category: category.trim(),
      operating_days: DAYS.filter((d) => days.has(d)),
      monthly_goal_centimes: centimes,
    };
    save.mutate(body);
  };

  const serverError = save.error instanceof ApiError ? save.error : null;
  const field = "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none disabled:bg-slate-50";

  return (
    <div className="max-w-2xl space-y-4">
      <Card title={t("profile.title")}>
        <dl className="mb-4 grid grid-cols-2 gap-2 text-xs text-slate-500">
          <div><dt>{t("profile.merchantId")}</dt><dd className="font-mono text-slate-800">{m.merchant_id}</dd></div>
          <div><dt>{t("profile.timezone")}</dt><dd className="text-slate-800">{m.timezone}</dd></div>
        </dl>
        {readOnly && <p className="mb-3 rounded-lg bg-sky-50 p-2 text-xs text-sky-800">{t("profile.readOnly")}</p>}

        <form onSubmit={submit} className="space-y-4" noValidate>
          <fieldset disabled={readOnly || save.isPending} className="space-y-4">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">{t("profile.displayName")}</span>
              <input className={field} value={name} maxLength={200} required
                onChange={(e) => setName(e.target.value)} />
            </label>

            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">{t("profile.category")}</span>
              <input className={field} value={category} maxLength={100} list="merchant-categories"
                onChange={(e) => setCategory(e.target.value)} />
              <datalist id="merchant-categories">
                {CATEGORY_SUGGESTIONS.map((c) => <option key={c} value={c} />)}
              </datalist>
            </label>

            <fieldset>
              <legend className="mb-1 text-sm font-medium text-slate-700">{t("profile.operatingDays")}</legend>
              <div className="flex flex-wrap gap-2">
                {DAYS.map((d) => (
                  <label key={d} className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm ${days.has(d)
                    ? "border-brand-600 bg-brand-50 text-brand-900" : "border-slate-300 text-slate-600"}`}>
                    <input type="checkbox" className="sr-only" checked={days.has(d)} onChange={() => toggle(d)} />
                    {formatWeekday(ISO_WEEKDAY[d], "short")}
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">{t("profile.monthlyGoal")}</span>
              <input className={field} value={goal} inputMode="decimal" placeholder="1 500 000"
                onChange={(e) => setGoal(e.target.value)} />
              <span className="mt-1 block text-xs text-slate-500">{t("profile.monthlyGoalHelp")}</span>
            </label>
          </fieldset>

          {(formError || serverError) && (
            <p role="alert" className="text-sm text-rose-700">{formError ?? t("profile.errors.server")}</p>
          )}
          {save.isSuccess && !save.isPending && (
            <p role="status" className="text-sm text-emerald-700">
              {t("profile.saved", { goal: formatMoney(save.data.monthly_goal) })}
            </p>
          )}
          {!readOnly && (
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? t("profile.saving") : t("profile.save")}
            </Button>
          )}
        </form>
      </Card>
    </div>
  );
}

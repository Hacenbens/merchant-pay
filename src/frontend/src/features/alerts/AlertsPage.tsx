import clsx from "clsx";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { Alert, AlertState } from "@/api/types";
import { Button, Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatDateTime, formatDzd, formatNumber, formatPct } from "@/lib/format";
import { useAlertTransition, useAlerts, useEvaluateAlerts } from "./api";
import { SeverityBadge } from "./SeverityBadge";

const STATES: AlertState[] = ["open", "acknowledged", "resolved"];

export function AlertsPage() {
  const { t } = useTranslation();
  const [state, setState] = useState<AlertState>("open");
  const [picked, setPicked] = useState<number | null>(null);
  const query = useAlerts(state);
  const evaluate = useEvaluateAlerts();
  const acknowledge = useAlertTransition("acknowledge");
  const resolve = useAlertTransition("resolve");

  const items = query.data?.items ?? [];
  const selected = items.find((a) => a.id === picked) ?? items[0] ?? null;

  const value = (a: Alert, raw: string | null) => {
    if (raw === null) return "—";
    if (a.unit === "rate") return formatPct(Number(raw));
    if (a.unit === "days") return `${formatNumber(Number(raw))} ${t("alerts.days")}`;
    return formatDzd(raw);
  };

  return (
    <div className="space-y-4">
      <Card
        title={t("alerts.title")}
        action={
          <div className="flex items-center gap-2">
            {evaluate.data && (
              <span className="text-xs text-muted-foreground">
                {t("alerts.evaluated", { count: evaluate.data.created.length })}
              </span>
            )}
            <Button variant="outline" className="text-xs" disabled={evaluate.isPending}
              onClick={() => evaluate.mutate()}>
              {evaluate.isPending ? t("alerts.evaluating") : t("alerts.evaluate")}
            </Button>
          </div>
        }
      >
        <div className="flex flex-wrap gap-2" role="tablist">
          {STATES.map((s) => (
            <button key={s} role="tab" aria-selected={state === s}
              onClick={() => { setState(s); setPicked(null); }}
              className={clsx("rounded-lg px-3 py-1.5 text-sm",
                state === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted")}>
              {t(`alerts.state.${s}`)}
              <span className="ms-2 tabular-nums opacity-80">{query.data?.counts[s] ?? 0}</span>
            </button>
          ))}
        </div>
        {evaluate.isError && <p className="mt-2 text-sm text-destructive">{t("common.error")}</p>}
      </Card>

      {query.isPending ? <Spinner /> : query.isError ? <ErrorState onRetry={() => query.refetch()} /> :
        items.length === 0 ? <EmptyState>{t("alerts.empty")}</EmptyState> : (
          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="lg:col-span-2" title={t(`alerts.state.${state}`)}>
              <ul className="divide-y divide-border">
                {items.map((a) => (
                  <li key={a.id}>
                    <button onClick={() => setPicked(a.id)} aria-current={selected?.id === a.id}
                      className={clsx("w-full rounded-lg px-2 py-2 text-start hover:bg-muted/50",
                        selected?.id === a.id && "bg-muted")}>
                      <span className="flex flex-wrap items-center gap-2">
                        <SeverityBadge severity={a.severity} />
                        <span className="text-sm font-medium text-foreground">
                          {t(`alerts.rules.${a.rule_code}`, { defaultValue: a.rule_code })}
                        </span>
                      </span>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {formatDate(a.window.date_from)} → {formatDate(a.window.date_to)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>

            <Card className="lg:col-span-3" title={t("alerts.detail")}>
              {selected ? (
                <div className="space-y-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={selected.severity} />
                    <span className="font-medium text-foreground">
                      {t(`alerts.rules.${selected.rule_code}`, { defaultValue: selected.rule_code })}
                    </span>
                    <span className="text-xs text-muted-foreground">{t(`alerts.state.${selected.state}`)}</span>
                  </div>
                  <p className="text-foreground">{selected.explanation}</p>

                  <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div>
                      <dt className="text-xs text-muted-foreground">{t("alerts.observed")}</dt>
                      <dd className="font-medium tabular-nums">{value(selected, selected.observed_value)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">{t("alerts.baseline")}</dt>
                      <dd className="tabular-nums">{value(selected, selected.baseline_value)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">{t("alerts.delta")}</dt>
                      <dd className="tabular-nums">{formatPct(selected.delta_pct, true)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">{t("alerts.window")}</dt>
                      <dd className="whitespace-nowrap text-xs">{formatDate(selected.window.date_from)} →{" "}
                        {formatDate(selected.window.date_to)}</dd>
                    </div>
                  </dl>

                  <Link className="inline-block text-primary hover:underline"
                    to={`/transactions?${selected.evidence_ref}`}>
                    {t("alerts.evidence")}
                  </Link>

                  <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
                    {selected.state === "open" && (
                      <Button disabled={acknowledge.isPending}
                        onClick={() => acknowledge.mutate(selected.id)}>{t("alerts.acknowledge")}</Button>
                    )}
                    {selected.state !== "resolved" && (
                      <Button variant="outline" disabled={resolve.isPending}
                        onClick={() => resolve.mutate(selected.id)}>{t("alerts.resolve")}</Button>
                    )}
                    {(acknowledge.isError || resolve.isError) && (
                      <span className="text-xs text-destructive">{t("common.error")}</span>
                    )}
                    <span className="ms-auto text-xs text-muted-foreground/70">
                      {formatDateTime(selected.created_at)}
                    </span>
                  </div>

                  <details className="rounded-lg bg-muted/50 p-2 text-xs text-muted-foreground">
                    <summary className="cursor-pointer font-medium">{t("alerts.method")}</summary>
                    <p className="mt-1">{t("alerts.methodBody")}</p>
                  </details>
                </div>
              ) : <EmptyState>{t("alerts.select")}</EmptyState>}
            </Card>
          </div>
        )}
    </div>
  );
}

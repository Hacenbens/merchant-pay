import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Decision, ReengageEntry } from "@/api/types";
import { today } from "@/app/filters";
import { Button, Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatMoney, toIsoDate } from "@/lib/format";
import { useRecordDecision, useReengagement } from "./api";
import { Evidence, StatusBadge } from "./Evidence";

/** Win-back radar: prioritised customers to re-engage. Suggestions only; nothing is ever sent. */
export function WinbackList({ windowDays, onOpen }: { windowDays: number; onOpen: (token: string) => void }) {
  const { t } = useTranslation();
  const [includeHidden, setIncludeHidden] = useState(false);
  const q = useReengagement(windowDays, includeHidden);
  return (
    <Card title={t("customers.winback.title")} action={
      <label className="flex items-center gap-1 text-xs text-muted-foreground">
        <input type="checkbox" checked={includeHidden} onChange={(e) => setIncludeHidden(e.target.checked)} />
        {t("customers.winback.showHidden", { n: q.data?.hidden_count ?? 0 })}
      </label>
    }>
      <p className="mb-3 text-sm text-muted-foreground">{t("customers.winback.intro")}</p>
      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> :
        q.data.entries.length === 0 ? <EmptyState>{t("customers.winback.empty")}</EmptyState> : (
          <ul className="divide-y divide-border">
            {q.data.entries.map((e) => <Entry key={e.customer.token} e={e} onOpen={onOpen} />)}
          </ul>
        )}
    </Card>
  );
}

function Entry({ e, onOpen }: { e: ReengageEntry; onOpen: (token: string) => void }) {
  const { t } = useTranslation();
  const record = useRecordDecision();
  const c = e.customer;
  const snoozeUntil = () => {  // one week from the app's "today" (frozen in the demo, like the API)
    const d = today();
    d.setDate(d.getDate() + 7);
    return toIsoDate(d);
  };
  const act = (decision: Decision) =>
    record.mutate({ token: c.token, decision, snoozeUntil: decision === "snooze" ? snoozeUntil() : undefined });

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button className="font-mono text-sm text-primary hover:underline" onClick={() => onOpen(c.token)}>{c.alias}</button>
          <StatusBadge status={c.evidence.status} />
          {c.high_value && <span className="text-xs text-amber-700 dark:text-amber-400">{t("customers.highValue")}</span>}
        </div>
        <span className="text-xs text-muted-foreground">
          {t("customers.winback.history", { value: formatMoney(c.monetary), n: c.frequency })}
        </span>
      </div>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        <Evidence e={c.evidence} />
        <div className="text-sm">
          <p className="font-medium text-foreground">{t(`customers.suggestion.${e.suggestion}`)}</p>
          <p className="text-xs text-muted-foreground">{t(`customers.suggestionWhy.${e.suggestion}`)}</p>
          {e.recheck_on && <p className="text-xs text-muted-foreground">{t("customers.winback.recheck", { date: formatDate(e.recheck_on) })}</p>}
          <p className="mt-1 text-xs text-muted-foreground">{t("customers.winback.mayBeWrong")}</p>
          {e.decision && (
            <p className="mt-1 text-xs text-foreground">
              {t(`customers.decision.${e.decision.decision}`, { date: e.decision.snooze_until ? formatDate(e.decision.snooze_until) : "" })}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            <Button variant="outline" className="text-xs" disabled={record.isPending} onClick={() => act("contacted")}>
              {t("customers.actions.contacted")}
            </Button>
            <Button variant="outline" className="text-xs" disabled={record.isPending} onClick={() => act("snooze")}>
              {t("customers.actions.snooze")}
            </Button>
            {e.decision ? (
              <Button variant="ghost" className="text-xs" disabled={record.isPending} onClick={() => act("clear")}>
                {t("customers.actions.clear")}
              </Button>
            ) : (
              <Button variant="ghost" className="text-xs" disabled={record.isPending} onClick={() => act("dismiss")}>
                {t("customers.actions.dismiss")}
              </Button>
            )}
          </div>
          {record.isError && <p role="alert" className="mt-1 text-xs text-destructive">{t("customers.actions.error")}</p>}
        </div>
      </div>
    </li>
  );
}

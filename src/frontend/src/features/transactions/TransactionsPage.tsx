import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";
import { CHANNELS, STATUSES, type Channel, type TransactionStatus } from "@/api/types";
import { useFilters } from "@/app/filters";
import { StatusBadge } from "@/components/StatusBadge";
import { Button, Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { formatDateTime, formatMoney } from "@/lib/format";
import { PAGE_SIZE, useTransactions } from "./api";
import { TransactionDrawer } from "./TransactionDrawer";

/** Ledger filters live in the URL so a dashboard/alert can deep-link here (e.g. ?status=declined). */
export function TransactionsPage() {
  const { t } = useTranslation();
  const filters = useFilters();
  const [params, setParams] = useSearchParams();
  // An alert's evidence link carries its own window; otherwise the global period filter applies.
  const dateFrom = params.get("date_from") ?? filters.dateFrom;
  const dateTo = params.get("date_to") ?? filters.dateTo;
  const status = params.getAll("status") as TransactionStatus[];
  const channel = params.getAll("channel") as Channel[];
  const q = params.get("q") ?? "";
  const page = Number(params.get("page") ?? 1);
  const selected = params.get("tx");

  const update = (mutate: (p: URLSearchParams) => void, resetPage = true) => {
    const next = new URLSearchParams(params);
    mutate(next);
    if (resetPage) next.delete("page");
    setParams(next, { replace: true });
  };
  const toggle = (key: "status" | "channel", value: string) => update((p) => {
    const values = p.getAll(key);
    p.delete(key);
    (values.includes(value) ? values.filter((v) => v !== value) : [...values, value]).forEach((v) => p.append(key, v));
  });

  const query = useTransactions({ dateFrom, dateTo, status, channel, q, page });
  const pages = query.data ? Math.max(1, Math.ceil(query.data.total / PAGE_SIZE)) : 1;
  const chip = (active: boolean) => clsx("rounded-full border px-2.5 py-1 text-xs",
    active ? "border-primary bg-primary text-primary-foreground" : "border-input bg-card text-muted-foreground hover:bg-muted/50");

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-col gap-3">
          <input type="search" placeholder={t("tx.search")} defaultValue={q}
            className="w-full rounded-lg border border-input px-3 py-2 text-sm md:max-w-sm"
            onChange={(e) => update((p) => (e.target.value ? p.set("q", e.target.value) : p.delete("q")))} />
          <div className="flex flex-wrap gap-2">
            {STATUSES.map((s) => <button key={s} className={chip(status.includes(s))} onClick={() => toggle("status", s)}>{t(`status.${s}`)}</button>)}
          </div>
          <div className="flex flex-wrap gap-2">
            {CHANNELS.map((c) => <button key={c} className={chip(channel.includes(c))} onClick={() => toggle("channel", c)}>{t(`channel.${c}`)}</button>)}
            <Button variant="ghost" className="ms-auto text-xs" onClick={() => setParams({}, { replace: true })}>{t("tx.reset")}</Button>
          </div>
        </div>
      </Card>

      <Card title={query.data ? t("tx.results", { count: query.data.total }) : undefined}>
        {query.isPending ? <Spinner /> : query.isError ? <ErrorState onRetry={() => query.refetch()} /> :
          query.data.items.length === 0 ? <EmptyState>{t("tx.empty")}</EmptyState> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-start text-xs uppercase text-muted-foreground">
                  <tr>{["id", "date", "amount", "channel", "status"].map((h) => <th key={h} className="px-2 py-2 text-start font-medium">{t(`tx.${h}`)}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {query.data.items.map((tx) => (
                    <tr key={tx.transaction_id} tabIndex={0} className="cursor-pointer hover:bg-muted/50 focus:bg-muted"
                      onClick={() => update((p) => p.set("tx", tx.transaction_id), false)}
                      onKeyDown={(e) => e.key === "Enter" && update((p) => p.set("tx", tx.transaction_id), false)}>
                      <td className="px-2 py-2 font-mono text-xs">{tx.transaction_id}</td>
                      <td className="px-2 py-2 whitespace-nowrap">{formatDateTime(tx.occurred_at)}</td>
                      <td className="px-2 py-2 tabular-nums font-medium">{formatMoney(tx.amount)}</td>
                      <td className="px-2 py-2">{t(`channel.${tx.channel}`)}</td>
                      <td className="px-2 py-2"><StatusBadge status={tx.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        <div className="mt-3 flex items-center justify-between text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => update((p) => p.set("page", String(page - 1)), false)}>{t("tx.prev")}</Button>
          <span className="text-muted-foreground">{t("tx.page", { page, pages })}</span>
          <Button variant="outline" disabled={page >= pages} onClick={() => update((p) => p.set("page", String(page + 1)), false)}>{t("tx.next")}</Button>
        </div>
      </Card>

      <TransactionDrawer id={selected} onClose={() => update((p) => p.delete("tx"), false)} />
    </div>
  );
}

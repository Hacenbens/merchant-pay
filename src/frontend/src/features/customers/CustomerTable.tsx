import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ReturnStatus, Segment } from "@/api/types";
import { Button, Card, EmptyState, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatMoney, formatNumber } from "@/lib/format";
import { useCustomers } from "./api";
import { SegmentBadge } from "./CustomersPage";
import { StatusBadge } from "./Evidence";

const SEGMENTS: Segment[] = ["new", "one_time", "active", "loyal", "at_risk", "lapsed"];
const STATUSES: ReturnStatus[] = ["normal", "watch", "at_risk", "lapsed", "insufficient_history", "not_repeat"];

/** RFM table: recency, frequency and value stay in separate columns; high value is only a flag. */
export function CustomerTable({ windowDays, onOpen }: { windowDays: number; onOpen: (token: string) => void }) {
  const { t } = useTranslation();
  const [segment, setSegment] = useState<Segment | "">("");
  const [status, setStatus] = useState<ReturnStatus | "">("");
  const [highValue, setHighValue] = useState(false);
  const [page, setPage] = useState(1);
  const q = useCustomers({ windowDays, segment: segment || undefined, status: status || undefined,
    highValue: highValue || undefined, page });
  const select = "rounded-lg border border-input px-2 py-1 text-sm";

  return (
    <Card title={t("customers.tableTitle")}>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
        <select className={select} value={segment} aria-label={t("customers.col.segment")}
          onChange={(e) => { setSegment(e.target.value as Segment | ""); setPage(1); }}>
          <option value="">{t("customers.allSegments")}</option>
          {SEGMENTS.map((s) => <option key={s} value={s}>{t(`customers.segment.${s}`)}</option>)}
        </select>
        <select className={select} value={status} aria-label={t("customers.col.status")}
          onChange={(e) => { setStatus(e.target.value as ReturnStatus | ""); setPage(1); }}>
          <option value="">{t("customers.allStatuses")}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{t(`customers.status.${s}`)}</option>)}
        </select>
        <label className="flex items-center gap-1 text-muted-foreground">
          <input type="checkbox" checked={highValue} onChange={(e) => { setHighValue(e.target.checked); setPage(1); }} />
          {t("customers.highValueOnly")}
        </label>
      </div>

      {q.isPending ? <Spinner /> : q.isError ? <ErrorState onRetry={() => q.refetch()} /> :
        q.data.items.length === 0 ? <EmptyState>{t("customers.noMatch")}</EmptyState> : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[44rem] text-sm">
                <thead className="text-xs text-muted-foreground">
                  <tr>
                    <th className="py-1 text-start font-medium">{t("customers.col.customer")}</th>
                    <th className="py-1 text-start font-medium">{t("customers.col.segment")}</th>
                    <th className="py-1 text-start font-medium">{t("customers.col.status")}</th>
                    <th className="py-1 text-end font-medium" title={t("customers.col.recencyHelp")}>{t("customers.col.recency")}</th>
                    <th className="py-1 text-end font-medium" title={t("customers.col.frequencyHelp")}>{t("customers.col.frequency")}</th>
                    <th className="py-1 text-end font-medium" title={t("customers.col.monetaryHelp")}>{t("customers.col.monetary")}</th>
                    <th className="py-1 text-end font-medium">{t("customers.col.last")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {q.data.items.map((p) => (
                    <tr key={p.token}>
                      <td className="py-2">
                        <button className="font-mono text-primary hover:underline" onClick={() => onOpen(p.token)}>
                          {p.alias}
                        </button>
                        {p.high_value && <span className="ms-2 text-xs text-amber-700 dark:text-amber-400">{t("customers.highValue")}</span>}
                      </td>
                      <td className="py-2"><SegmentBadge segment={p.segment} /></td>
                      <td className="py-2"><StatusBadge status={p.evidence.status} /></td>
                      <td className="py-2 text-end tabular-nums">{t("customers.daysShort", { n: p.recency_days })}</td>
                      <td className="py-2 text-end tabular-nums">{formatNumber(p.frequency)}</td>
                      <td className="py-2 text-end tabular-nums">{formatMoney(p.monetary)}</td>
                      <td className="py-2 text-end text-muted-foreground">{formatDate(p.last_purchase)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>{t("customers.pageInfo", { total: q.data.total, page: q.data.page,
                pages: Math.max(1, Math.ceil(q.data.total / q.data.size)) })}</span>
              <span className="flex gap-2">
                <Button variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("customers.prev")}</Button>
                <Button variant="outline" disabled={page * q.data.size >= q.data.total}
                  onClick={() => setPage(page + 1)}>{t("customers.next")}</Button>
              </span>
            </div>
          </>
        )}
    </Card>
  );
}

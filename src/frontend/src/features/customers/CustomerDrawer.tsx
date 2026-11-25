import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { StatusBadge as TxStatusBadge } from "@/components/StatusBadge";
import { Button, ErrorState, Spinner } from "@/components/ui";
import { formatDate, formatDateTime, formatMoney, formatNumber } from "@/lib/format";
import { useCustomer } from "./api";
import { SegmentBadge } from "./CustomersPage";
import { Evidence, StatusBadge } from "./Evidence";

/** One pseudonymous customer: RFM, return-gap evidence and their own transactions (all statuses). */
export function CustomerDrawer({ token, windowDays, onClose }: {
  token: string | null; windowDays: number; onClose: () => void;
}) {
  const { t } = useTranslation();
  const q = useCustomer(token, windowDays);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  if (!token) return null;

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/30" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-label={t("customers.detail")}
        className="h-full w-full max-w-md overflow-y-auto bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">{q.data ? q.data.customer.alias : t("customers.detail")}</h2>
          <Button variant="ghost" onClick={onClose}>{t("tx.close")}</Button>
        </div>
        {q.isPending ? <Spinner /> : q.isError ? <ErrorState /> : (() => {
          const c = q.data.customer;
          return (
            <div className="space-y-4 text-sm">
              <div className="flex flex-wrap gap-2">
                <SegmentBadge segment={c.segment} />
                <StatusBadge status={c.evidence.status} />
                {c.high_value && <span className="text-xs text-amber-700">{t("customers.highValue")}</span>}
              </div>
              <dl className="grid grid-cols-[9rem_1fr] gap-y-2">
                <dt className="text-slate-500">{t("customers.col.recency")}</dt>
                <dd>{t("customers.daysShort", { n: c.recency_days })}</dd>
                <dt className="text-slate-500">{t("customers.col.frequency")}</dt>
                <dd>{formatNumber(c.frequency)} <span className="text-xs text-slate-500">
                  {t("customers.inWindow", { days: q.data.book.rules.window_days })}</span></dd>
                <dt className="text-slate-500">{t("customers.col.monetary")}</dt>
                <dd>{formatMoney(c.monetary)}</dd>
                <dt className="text-slate-500">{t("customers.firstSeen")}</dt>
                <dd>{formatDate(c.first_purchase)} · {t("customers.lifetime", { n: c.lifetime_purchases })}</dd>
              </dl>
              <section>
                <h3 className="mb-1 text-xs font-medium text-slate-500">{t("customers.evidenceTitle")}</h3>
                <Evidence e={c.evidence} />
              </section>
              <section>
                <h3 className="mb-1 text-xs font-medium text-slate-500">{t("customers.byStatus")}</h3>
                <ul className="flex flex-wrap gap-3 text-xs">
                  {q.data.statuses.filter((s) => s.count > 0).map((s) => (
                    <li key={s.status} className="flex items-center gap-1">
                      <TxStatusBadge status={s.status} /> {formatNumber(s.count)} · {formatMoney(s.amount)}
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-xs text-slate-500">{t("customers.refundNote")}</p>
              </section>
              <section>
                <h3 className="mb-1 text-xs font-medium text-slate-500">{t("customers.recent")}</h3>
                <ul className="divide-y divide-slate-100">
                  {q.data.recent.map((tx) => (
                    <li key={tx.transaction_id} className="flex items-center justify-between gap-2 py-1.5 text-xs">
                      <span className="text-slate-600">{formatDateTime(tx.occurred_at)}</span>
                      <TxStatusBadge status={tx.status} />
                      <span className="tabular-nums">{formatMoney(tx.amount)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          );
        })()}
      </aside>
    </div>
  );
}

import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "@/components/motion";
import { isRtl } from "@/i18n";
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

  const rtl = isRtl();
  return (
    <AnimatePresence>
      {token && (
    <motion.div key="overlay" className="fixed inset-0 z-50 flex justify-end bg-black/10 supports-backdrop-filter:backdrop-blur-xs"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} onClick={onClose}>
      <motion.aside initial={{ x: rtl ? "-100%" : "100%" }} animate={{ x: 0 }} exit={{ x: rtl ? "-100%" : "100%" }}
        transition={{ type: "spring", stiffness: 400, damping: 40 }} role="dialog" aria-modal="true" aria-label={t("customers.detail")}
        className="h-full w-full max-w-md overflow-y-auto border-s bg-background p-5 shadow-lg" onClick={(e) => e.stopPropagation()}>
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
                {c.high_value && <span className="text-xs text-amber-700 dark:text-amber-400">{t("customers.highValue")}</span>}
              </div>
              <dl className="grid grid-cols-[9rem_1fr] gap-y-2">
                <dt className="text-muted-foreground">{t("customers.col.recency")}</dt>
                <dd>{t("customers.daysShort", { n: c.recency_days })}</dd>
                <dt className="text-muted-foreground">{t("customers.col.frequency")}</dt>
                <dd>{formatNumber(c.frequency)} <span className="text-xs text-muted-foreground">
                  {t("customers.inWindow", { days: q.data.book.rules.window_days })}</span></dd>
                <dt className="text-muted-foreground">{t("customers.col.monetary")}</dt>
                <dd>{formatMoney(c.monetary)}</dd>
                <dt className="text-muted-foreground">{t("customers.firstSeen")}</dt>
                <dd>{formatDate(c.first_purchase)} · {t("customers.lifetime", { n: c.lifetime_purchases })}</dd>
              </dl>
              <section>
                <h3 className="mb-1 text-xs font-medium text-muted-foreground">{t("customers.evidenceTitle")}</h3>
                <Evidence e={c.evidence} />
              </section>
              <section>
                <h3 className="mb-1 text-xs font-medium text-muted-foreground">{t("customers.byStatus")}</h3>
                <ul className="flex flex-wrap gap-3 text-xs">
                  {q.data.statuses.filter((s) => s.count > 0).map((s) => (
                    <li key={s.status} className="flex items-center gap-1">
                      <TxStatusBadge status={s.status} /> {formatNumber(s.count)} · {formatMoney(s.amount)}
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-xs text-muted-foreground">{t("customers.refundNote")}</p>
              </section>
              <section>
                <h3 className="mb-1 text-xs font-medium text-muted-foreground">{t("customers.recent")}</h3>
                <ul className="divide-y divide-border">
                  {q.data.recent.map((tx) => (
                    <li key={tx.transaction_id} className="flex items-center justify-between gap-2 py-1.5 text-xs">
                      <span className="text-muted-foreground">{formatDateTime(tx.occurred_at)}</span>
                      <TxStatusBadge status={tx.status} />
                      <span className="tabular-nums">{formatMoney(tx.amount)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          );
        })()}
      </motion.aside>
    </motion.div>
      )}
    </AnimatePresence>
  );
}

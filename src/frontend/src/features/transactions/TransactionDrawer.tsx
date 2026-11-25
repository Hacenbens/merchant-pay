import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "@/components/motion";
import { isRtl } from "@/i18n";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge, Button, ErrorState, Spinner } from "@/components/ui";
import { formatDateTime, formatMoney } from "@/lib/format";
import { useTransaction } from "./api";

export function TransactionDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { t } = useTranslation();
  const q = useTransaction(id);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const rtl = isRtl();
  return (
    <AnimatePresence>
      {id && (
    <motion.div key="overlay" className="fixed inset-0 z-50 flex justify-end bg-black/10 supports-backdrop-filter:backdrop-blur-xs"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} onClick={onClose}>
      <motion.aside initial={{ x: rtl ? "-100%" : "100%" }} animate={{ x: 0 }} exit={{ x: rtl ? "-100%" : "100%" }}
        transition={{ type: "spring", stiffness: 400, damping: 40 }} role="dialog" aria-modal="true" aria-label={t("tx.detail")}
        className="h-full w-full max-w-md overflow-y-auto border-s bg-background p-5 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">{t("tx.detail")}</h2>
          <Button variant="ghost" onClick={onClose}>{t("tx.close")}</Button>
        </div>
        {q.isPending ? <Spinner /> : q.isError ? <ErrorState /> : (
          <dl className="grid grid-cols-[8rem_1fr] gap-y-3 text-sm">
            <dt className="text-muted-foreground">{t("tx.id")}</dt><dd className="font-mono text-xs">{q.data.transaction_id}</dd>
            <dt className="text-muted-foreground">{t("tx.date")}</dt><dd>{formatDateTime(q.data.occurred_at)}</dd>
            <dt className="text-muted-foreground">{t("tx.amount")}</dt><dd className="font-semibold">{formatMoney(q.data.amount)}</dd>
            <dt className="text-muted-foreground">{t("tx.channel")}</dt><dd>{t(`channel.${q.data.channel}`)}</dd>
            <dt className="text-muted-foreground">{t("tx.status")}</dt><dd><StatusBadge status={q.data.status} /></dd>
            <dt className="text-muted-foreground">{t("tx.category")}</dt><dd>{q.data.category}</dd>
            <dt className="text-muted-foreground">{t("tx.origin")}</dt>
            <dd><Badge tone={q.data.data_origin === "synthetic_demo" ? "warning" : "neutral"}>{t(`origin.${q.data.data_origin}`)}</Badge></dd>
            <dt className="text-muted-foreground">{t("tx.batch")}</dt><dd className="break-all font-mono text-xs">{q.data.source_batch_id}</dd>
          </dl>
        )}
      </motion.aside>
    </motion.div>
      )}
    </AnimatePresence>
  );
}

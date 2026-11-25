import { useTranslation } from "react-i18next";
import type { ReturnEvidence, ReturnStatus } from "@/api/types";
import { Badge } from "@/components/ui";
import { formatDate, formatNumber } from "@/lib/format";

const STATUS_TONE: Record<ReturnStatus, "success" | "warning" | "danger" | "neutral" | "info"> = {
  normal: "success", watch: "info", at_risk: "warning", lapsed: "danger",
  insufficient_history: "neutral", not_repeat: "neutral",
};

export function StatusBadge({ status }: { status: ReturnStatus }) {
  const { t } = useTranslation();
  return <Badge tone={STATUS_TONE[status]}>{t(`customers.status.${status}`)}</Badge>;
}

const days = (d: number) => formatNumber(Math.round(d * 10) / 10);

/** The exact evidence behind a win-back status. Never a probability. */
export function Evidence({ e }: { e: ReturnEvidence }) {
  const { t } = useTranslation();
  const b = e.baseline;
  const th = e.thresholds;
  return (
    <div className="space-y-1 text-xs text-muted-foreground">
      <p>
        {t("customers.evidence.gap", { last: formatDate(e.last_purchase), gap: e.gap_days, visits: e.purchase_days })}
      </p>
      {b ? (
        <p>
          {t(`customers.evidence.baseline_${b.source}`, { median: days(b.median_days), spread: days(b.spread_days),
            n: b.intervals })}
          {e.ratio !== null && <> {t("customers.evidence.ratio", { ratio: days(e.ratio) })}</>}
        </p>
      ) : (
        <p>{t(e.status === "not_repeat" ? "customers.evidence.notRepeat" : "customers.evidence.noBaseline")}</p>
      )}
      {th && (
        <p>{t("customers.evidence.thresholds", { watch: days(th.watch_days), risk: days(th.at_risk_days),
          lapsed: days(th.lapsed_days) })}</p>
      )}
      <p className="text-muted-foreground/70">{t("customers.evidence.rule", { version: e.rule_version })}</p>
    </div>
  );
}

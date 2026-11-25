import { MinusIcon, TrendingDownIcon, TrendingUpIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { Change } from "@/api/types";
import { itemVariants, motion } from "@/components/motion";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Stat card in the shadcn-fintech style: muted label, large tabular value, change pill. */
export function KpiCard({ label, value, change, footnote, help }: {
  label: string; value: ReactNode; change?: Change; footnote?: ReactNode; help?: string;
}) {
  const { t } = useTranslation();
  const pct = change?.kind === "comparable" ? change.pct ?? 0 : null;
  const Icon = pct === null ? MinusIcon : pct < 0 ? TrendingDownIcon : TrendingUpIcon;
  return (
    <motion.div variants={itemVariants} title={help}
      className="flex flex-col gap-2 rounded-xl bg-card p-4 text-card-foreground ring-1 ring-foreground/10">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      {change && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <span className={cn("inline-flex h-5 items-center gap-1 rounded-4xl px-2 font-medium",
            pct === null ? "bg-secondary text-secondary-foreground"
              : pct < 0 ? "bg-destructive/10 text-destructive" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400")}>
            <Icon className="size-3" />
            {pct === null ? t(change.kind === "new_activity" ? "kpi.newActivity" : "kpi.noActivity") : formatPct(pct, true)}
          </span>
          {t("kpi.vsPrevious")}
        </div>
      )}
      {footnote && <p className="text-xs text-muted-foreground">{footnote}</p>}
    </motion.div>
  );
}

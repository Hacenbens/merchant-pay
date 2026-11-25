/**
 * App-level building blocks with the original props, rendered with the shadcn-fintech primitives
 * (./card, ./button, ./badge, ./skeleton). Every page keeps its imports; the look and motion come from here.
 */
import { AlertTriangleIcon, InboxIcon, RotateCcwIcon } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { itemVariants, motion } from "@/components/motion";
import { Badge as ShadBadge } from "./badge";
import { Button as ShadButton } from "./button";
import { CardAction, CardContent, CardHeader, CardTitle } from "./card";
import { Skeleton } from "./skeleton";

/** A card that joins the page stagger (fade + 12 px rise). Same props as before. */
export function Card({ title, action, children, className }: {
  title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <motion.section
      variants={itemVariants}
      data-slot="card"
      className={cn("group/card flex flex-col gap-4 overflow-hidden rounded-xl bg-card py-4 text-sm text-card-foreground ring-1 ring-foreground/10",
        className)}
    >
      {(title || action) && (
        <CardHeader>
          {title && <CardTitle className="text-base font-semibold">{title}</CardTitle>}
          {action && <CardAction>{action}</CardAction>}
        </CardHeader>
      )}
      <CardContent>{children}</CardContent>
    </motion.section>
  );
}

const BUTTON_VARIANT = { primary: "default", outline: "outline", ghost: "ghost" } as const;

export function Button({ variant = "primary", className, ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof BUTTON_VARIANT }) {
  return <ShadButton variant={BUTTON_VARIANT[variant]} className={className} {...props} />;
}

// Tinted pills in the reference style; strong colour stays reserved for alerts and risk.
const TONES = {
  neutral: "bg-secondary text-secondary-foreground",
  success: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  danger: "bg-destructive/10 text-destructive dark:bg-destructive/20",
  warning: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  info: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
} as const;

export function Badge({ tone = "neutral", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return <ShadBadge variant="secondary" className={TONES[tone]}>{children}</ShadBadge>;
}

/** Loading state: skeleton bars (the reference uses skeleton layouts, never spinners). */
export function Spinner({ rows = 3 }: { rows?: number }) {
  const { t } = useTranslation();
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3 py-2">
      <span className="sr-only">{t("common.loading")}</span>
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className={cn("h-4", i % 2 ? "w-2/3" : "w-full")} />)}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: "easeOut" }}
      className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-10 text-center">
      <motion.div initial={{ scale: 0.85 }} animate={{ scale: 1 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <InboxIcon className="size-5" />
      </motion.div>
      <motion.p initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
        className="max-w-sm px-4 text-sm text-muted-foreground">{children}</motion.p>
    </motion.div>
  );
}

export function ErrorState({ onRetry }: { onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} role="alert"
      className="flex items-center gap-3 rounded-xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
      <AlertTriangleIcon className="size-4 shrink-0" />
      <span className="flex-1">{t("common.error")}</span>
      {onRetry && (
        <ShadButton variant="ghost" size="sm" onClick={onRetry} className="text-destructive hover:bg-destructive/10">
          <RotateCcwIcon />{t("common.retry")}
        </ShadButton>
      )}
    </motion.div>
  );
}

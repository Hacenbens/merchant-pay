/**
 * Motion vocabulary, taken from shadcn-fintech (MIT) so every page moves the same way:
 * - page:     fade + 8px rise on enter, fade + 8px lift on exit (0.2 s)
 * - stagger:  children reveal 0.06 s apart, after 0.1 s
 * - item:     fade + 12px rise over 0.4 s, ease [0.25, 0.46, 0.45, 0.94]
 * - pop:      spring scale-in for icons and badges (stiffness 300, damping 20)
 * Components that declare `variants` (Card, KpiCard, list rows) join the nearest stagger automatically.
 * Users who ask the OS for reduced motion get instant transitions (MotionConfig reducedMotion="user").
 */
import { AnimatePresence, MotionConfig, motion, type Variants } from "motion/react";
import type { ReactNode } from "react";

export const EASE = [0.25, 0.46, 0.45, 0.94] as const;

export const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.06, delayChildren: 0.1 } },
};

export const itemVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE } },
};

export const rowVariants: Variants = {
  hidden: { opacity: 0, y: 4 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.25, ease: EASE } },
};

export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

/** Route-level transition: wraps the outlet, keyed by pathname. Also the root of the page stagger. */
export function PageTransition({ routeKey, children }: { routeKey: string; children: ReactNode }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={routeKey}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.2, ease: EASE }}
        className="flex flex-1 flex-col"
      >
        <motion.div variants={containerVariants} initial="hidden" animate="visible" className="flex flex-1 flex-col">
          {children}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

/** A local stagger group (e.g. a list or grid that appears after data loads). */
export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={containerVariants} initial="hidden" animate="visible" className={className}>
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div variants={itemVariants} className={className}>{children}</motion.div>;
}

/** Cross-fade between keyed content (tabs, result swaps). */
export function Swap({ id, children, className }: { id: string; children: ReactNode; className?: string }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div key={id} className={className} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2, ease: EASE }}>
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export { AnimatePresence, motion };

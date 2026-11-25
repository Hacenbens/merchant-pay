/** Chart helpers in the shadcn-fintech style (square dots, theme colours). Display geometry only. */
import { isRtl } from "@/i18n";

type DotProps = { cx?: number; cy?: number; fill?: string; opacity?: number; size?: number };

export function SquareDot({ cx, cy, fill, opacity = 1, size = 6 }: DotProps) {
  if (cx == null || cy == null) return null;
  return <rect x={cx - size / 2} y={cy - size / 2} width={size} height={size} fill={fill} fillOpacity={opacity} rx={1} />;
}

/** Arabic compact numbers ("1,2 مليون") are wider than Latin ones: give the value axis room. */
export const axisWidth = () => (isRtl() ? 72 : 48);

export const CHART_PRIMARY = "var(--color-primary)";

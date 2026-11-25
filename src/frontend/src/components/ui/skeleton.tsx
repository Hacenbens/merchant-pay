// Adapted from shadcn-fintech (MIT, (c) 2026 Abderrahim Ghazali), built on shadcn/ui (MIT).
import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }

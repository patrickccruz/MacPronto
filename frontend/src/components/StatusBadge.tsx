import { cn } from "cn"

import { STATUS_LABEL, STATUS_STYLE } from "@/lib/labels"
import type { ComponentStatus } from "@/lib/types"

export function StatusBadge({ status, label, className }: { status: ComponentStatus; label?: string; className?: string }) {
  const style = STATUS_STYLE[status]
  return (
    <span
      className={cn(
        "inline-flex h-6 shrink-0 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium whitespace-nowrap",
        style.bg,
        style.border,
        style.text,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", style.dot)} />
      {label ?? STATUS_LABEL[status]}
    </span>
  )
}

export function StatusDot({ status, className }: { status: ComponentStatus; className?: string }) {
  return <span className={cn("inline-block size-2 shrink-0 rounded-full", STATUS_STYLE[status].dot, className)} />
}

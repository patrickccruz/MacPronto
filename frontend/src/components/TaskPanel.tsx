import { CircleCheck, LoaderCircle, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { type TaskState, taskPercent } from "@/lib/useTask"

export function TaskPanel({
  task,
  title,
  onCancel,
  hint,
}: {
  task: TaskState
  title: string
  onCancel?: () => void
  hint?: string
}) {
  const value = taskPercent(task.progress)
  const previous = task.stages.slice(0, -1).slice(-5)

  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-5 pt-1">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <LoaderCircle className="mt-0.5 size-5 animate-spin text-primary" />
            <div className="space-y-1">
              <p className="font-medium">{title}</p>
              <p className="text-sm text-muted-foreground">{task.stage ?? "Preparando..."}</p>
            </div>
          </div>
          {onCancel && (
            <Button variant="ghost" size="sm" onClick={onCancel}>
              <X data-icon="inline-start" />
              Cancelar
            </Button>
          )}
        </div>

        <div className="space-y-2">
          <Progress value={value ?? undefined} className={value === null ? "animate-pulse" : undefined} />
          <div className="flex justify-between text-xs text-muted-foreground tabular-nums">
            <span className="truncate">{task.progress?.label ?? ""}</span>
            {value !== null && <span>{value}%</span>}
          </div>
        </div>

        {previous.length > 0 && (
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            {previous.map((stage) => (
              <li key={stage} className="flex items-center gap-2">
                <CircleCheck className="size-4 text-native" />
                {stage}
              </li>
            ))}
          </ul>
        )}

        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  )
}

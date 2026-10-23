import { CircleCheckBig, CircleX, LoaderCircle, X } from "lucide-react"
import { cn } from "cn"
import { useEffect } from "react"

import { Progress } from "@/components/ui/progress"
import { type BackgroundTask, useBackgroundTasks } from "@/lib/backgroundTasks"
import { useApp } from "@/lib/store"
import { taskPercent } from "@/lib/useTask"

function DockCard({ task, onOpen, onDismiss }: { task: BackgroundTask; onOpen: () => void; onDismiss: () => void }) {
  const value = taskPercent(task.progress)
  const failed = task.finished && task.error && task.error.code !== "cancelled"
  const cancelled = task.finished && task.error?.code === "cancelled"
  const Icon = task.running ? LoaderCircle : failed || cancelled ? CircleX : CircleCheckBig

  return (
    <div className="group relative overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lg ring-1 ring-foreground/5">
      <button type="button" onClick={onOpen} className="block w-full space-y-2 p-3 pr-9 text-left hover:bg-accent/50">
        <span className="flex items-center gap-2 text-sm font-medium">
          <Icon
            className={cn(
              "size-4 shrink-0",
              task.running && "animate-spin text-primary",
              failed && "text-incompatible",
              cancelled && "text-muted-foreground",
              task.finished && !task.error && "text-native",
            )}
          />
          <span className="truncate">{task.title}</span>
          {task.running && value !== null && <span className="ml-auto shrink-0 tabular-nums">{value}%</span>}
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          {task.running
            ? (task.stage ?? "Preparando...")
            : failed
              ? `Falhou: ${task.error?.message}`
              : cancelled
                ? "Cancelado"
                : "Concluído. Clique para ver."}
        </span>
        {task.running && <Progress value={value ?? undefined} className={cn("h-1", value === null && "animate-pulse")} />}
      </button>
      {task.finished && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Fechar"
          className="absolute top-2 right-2 rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <X className="size-3.5" />
        </button>
      )}
    </div>
  )
}

/** Cartões das tarefas em andamento (ou recém-terminadas) que estão fora da tela atual. */
export function TaskDock() {
  const { view, go } = useApp()
  const { tasks, markSeen } = useBackgroundTasks()

  // Ao abrir a tela da tarefa, o resultado conta como visto
  useEffect(() => {
    for (const task of Object.values(tasks)) {
      if (task.view === view && task.finished && !task.seen) markSeen(task.key)
    }
  }, [tasks, view, markSeen])

  const visible = Object.values(tasks).filter((task) => task.view !== view && (task.running || (task.finished && !task.seen)))
  if (visible.length === 0) return null

  return (
    <div className="fixed bottom-4 left-[17rem] z-50 flex w-80 flex-col gap-2" aria-live="polite">
      {visible.map((task) => (
        <DockCard
          key={task.key}
          task={task}
          onOpen={() => {
            go(task.view)
            if (task.finished) markSeen(task.key)
          }}
          onDismiss={() => markSeen(task.key)}
        />
      ))}
    </div>
  )
}


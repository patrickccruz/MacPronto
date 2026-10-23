import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { api } from "./api"
import { BridgeError, newTaskId, onTaskEvent } from "./bridge"
import type { TaskEvent } from "./types"

export interface TaskState {
  running: boolean
  stage: string | null
  stages: string[]
  progress: { current: number; total: number; label: string } | null
  logs: { level: string; message: string }[]
  error: BridgeError | null
}

export const IDLE_TASK: TaskState = { running: false, stage: null, stages: [], progress: null, logs: [], error: null }

/** Aplica um evento de progresso do backend ao estado de uma tarefa. */
export function reduceTaskEvent<S extends TaskState>(previous: S, event: TaskEvent): S {
  if (event.kind === "stage" && event.data.title) {
    const stages = previous.stages.at(-1) === event.data.title ? previous.stages : [...previous.stages, event.data.title]
    return { ...previous, stage: event.data.title, stages, progress: null }
  }
  if (event.kind === "progress") {
    return {
      ...previous,
      progress: { current: event.data.current ?? 0, total: event.data.total ?? 0, label: event.data.label ?? "" },
    }
  }
  if (event.kind === "log" && event.data.message) {
    return { ...previous, logs: [...previous.logs.slice(-60), { level: event.data.level ?? "info", message: event.data.message }] }
  }
  return previous
}

/** Porcentagem do progresso, ou null quando o total é desconhecido. */
export function taskPercent(progress: TaskState["progress"]) {
  if (!progress || !progress.total) return null
  return Math.max(0, Math.min(100, Math.round((progress.current / progress.total) * 100)))
}

export function toBridgeError(error: unknown) {
  return error instanceof BridgeError ? error : new BridgeError("unexpected", String(error))
}

/** Tarefa ligada a uma tela: o estado some quando a tela é fechada. Para tarefas longas, use useBackgroundTask. */
export function useTask() {
  const [state, setState] = useState<TaskState>(IDLE_TASK)
  const currentId = useRef<string | null>(null)

  useEffect(
    () =>
      onTaskEvent((event) => {
        if (event.taskId !== currentId.current) return
        setState((previous) => reduceTaskEvent(previous, event))
      }),
    [],
  )

  const run = useCallback(async <T,>(prefix: string, fn: (taskId: string) => Promise<T>): Promise<T | undefined> => {
    const taskId = newTaskId(prefix)
    currentId.current = taskId
    setState({ ...IDLE_TASK, running: true })
    try {
      const result = await fn(taskId)
      setState((previous) => ({ ...previous, running: false }))
      return result
    } catch (error) {
      const bridgeError = toBridgeError(error)
      setState((previous) => ({ ...previous, running: false, error: bridgeError }))
      if (bridgeError.code !== "cancelled") toast.error(bridgeError.message)
      return undefined
    } finally {
      if (currentId.current === taskId) currentId.current = null
    }
  }, [])

  const cancel = useCallback(() => {
    if (currentId.current) void api.cancel(currentId.current)
  }, [])

  const reset = useCallback(() => setState(IDLE_TASK), [])

  return { ...state, run, cancel, reset }
}

export type TaskHandle = ReturnType<typeof useTask>

// Tarefas longas (diagnóstico, EFI, pendrive) que continuam visíveis quando o usuário troca de tela.
// O estado fica aqui, acima das telas: ao voltar para a tela, o progresso reaparece; nas outras
// telas, o TaskDock mostra um cartão com a porcentagem.

import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { api } from "./api"
import { newTaskId, onTaskEvent } from "./bridge"
import type { ViewId } from "./steps"
import { IDLE_TASK, reduceTaskEvent, type TaskState, toBridgeError } from "./useTask"

export interface BackgroundTask extends TaskState {
  key: string
  taskId: string
  title: string
  view: ViewId
  result: unknown
  finished: boolean
  /** O usuário já viu o resultado (estava na tela ou clicou no cartão). */
  seen: boolean
}

interface StartOptions {
  title: string
  view: ViewId
}

interface BackgroundTasksValue {
  tasks: Record<string, BackgroundTask>
  start: <T>(key: string, options: StartOptions, fn: (taskId: string) => Promise<T>) => Promise<T | undefined>
  cancel: (key: string) => void
  dismiss: (key: string) => void
  markSeen: (key: string) => void
}

const BackgroundTasksContext = createContext<BackgroundTasksValue | null>(null)

export function BackgroundTasksProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<Record<string, BackgroundTask>>({})
  const running = useRef(new Map<string, string>()) // key -> taskId das tarefas em andamento

  useEffect(
    () =>
      onTaskEvent((event) => {
        setTasks((previous) => {
          const key = Object.keys(previous).find((name) => previous[name].taskId === event.taskId)
          if (!key) return previous
          return { ...previous, [key]: reduceTaskEvent(previous[key], event) }
        })
      }),
    [],
  )

  const update = useCallback((key: string, taskId: string, changes: Partial<BackgroundTask>) => {
    setTasks((previous) => {
      const current = previous[key]
      if (!current || current.taskId !== taskId) return previous
      return { ...previous, [key]: { ...current, ...changes } }
    })
  }, [])

  const start = useCallback(
    async <T,>(key: string, options: StartOptions, fn: (taskId: string) => Promise<T>): Promise<T | undefined> => {
      if (running.current.has(key)) {
        toast.info(`${options.title}: já está em andamento.`)
        return undefined
      }
      const taskId = newTaskId(key)
      running.current.set(key, taskId)
      setTasks((previous) => ({
        ...previous,
        [key]: { ...IDLE_TASK, running: true, key, taskId, title: options.title, view: options.view, result: undefined, finished: false, seen: false },
      }))
      try {
        const result = await fn(taskId)
        update(key, taskId, { running: false, finished: true, result })
        return result
      } catch (error) {
        const bridgeError = toBridgeError(error)
        update(key, taskId, { running: false, finished: true, error: bridgeError })
        if (bridgeError.code !== "cancelled") toast.error(bridgeError.message)
        return undefined
      } finally {
        running.current.delete(key)
      }
    },
    [update],
  )

  const cancel = useCallback((key: string) => {
    const taskId = running.current.get(key)
    if (taskId) void api.cancel(taskId)
  }, [])

  const dismiss = useCallback((key: string) => {
    if (running.current.has(key)) return
    setTasks((previous) => {
      const next = { ...previous }
      delete next[key]
      return next
    })
  }, [])

  const markSeen = useCallback((key: string) => {
    setTasks((previous) => (previous[key] && !previous[key].seen ? { ...previous, [key]: { ...previous[key], seen: true } } : previous))
  }, [])

  const value = useMemo(() => ({ tasks, start, cancel, dismiss, markSeen }), [tasks, start, cancel, dismiss, markSeen])
  return <BackgroundTasksContext.Provider value={value}>{children}</BackgroundTasksContext.Provider>
}

export function useBackgroundTasks() {
  const context = useContext(BackgroundTasksContext)
  if (!context) throw new Error("useBackgroundTasks precisa estar dentro de BackgroundTasksProvider")
  return context
}

/** Diz se a tela ainda está aberta (para não navegar depois que o usuário saiu dela). */
export function useMountedRef() {
  const mounted = useRef(false)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])
  return mounted
}

/** Acesso a uma tarefa pelo nome (ex.: "pendrive"). */
export function useBackgroundTask(key: string) {
  const { tasks, start, cancel, dismiss } = useBackgroundTasks()
  const task = tasks[key]
  return {
    task,
    running: Boolean(task?.running),
    run: <T,>(options: StartOptions, fn: (taskId: string) => Promise<T>) => start(key, options, fn),
    cancel: () => cancel(key),
    dismiss: () => dismiss(key),
  }
}

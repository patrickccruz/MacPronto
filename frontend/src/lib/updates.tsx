// Atualização automática: o backend procura versões novas a cada minuto e avisa por evento.
// Este contexto guarda a situação e controla o aviso de versão nova (UpdateDialog).

import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import { api } from "./api"
import { BridgeError, onTaskEvent } from "./bridge"
import type { UpdateStatus } from "./types"

interface UpdatesValue {
  status: UpdateStatus | null
  dialogOpen: boolean
  openDialog: () => void
  /** "Depois": fecha e não abre sozinho de novo para esta versão. */
  postpone: () => void
  checkNow: () => Promise<void>
}

const UpdatesContext = createContext<UpdatesValue | null>(null)

export function UpdatesProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<UpdateStatus | null>(null)
  const [manualOpen, setManualOpen] = useState(false)
  const [postponed, setPostponed] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const load = () =>
      api.updateStatus().then(
        (next) => {
          if (active) setStatus(next)
        },
        () => undefined,
      )
    void load()
    // Reserva: se um evento se perder, a situação chega na leitura seguinte
    const timer = window.setInterval(() => void load(), 60_000)
    const off = onTaskEvent((event) => {
      if (event.kind === "update") setStatus(event.data as unknown as UpdateStatus)
    })
    return () => {
      active = false
      window.clearInterval(timer)
      off()
    }
  }, [])

  const version = status?.available?.version ?? null
  // O aviso abre sozinho uma vez para cada versão nova
  const dialogOpen = version !== null && (manualOpen || version !== postponed)

  const openDialog = useCallback(() => setManualOpen(true), [])
  const postpone = useCallback(() => {
    setManualOpen(false)
    setPostponed(version)
  }, [version])

  const checkNow = useCallback(async () => {
    try {
      const next = await api.updateCheck()
      setStatus(next)
      if (next.error) toast.error(next.error)
      else if (next.available) setManualOpen(true)
      else toast.success(`Você já está na versão mais nova (${next.current}).`)
    } catch (error) {
      toast.error(error instanceof BridgeError ? error.message : String(error))
    }
  }, [])

  const value = useMemo(
    () => ({ status, dialogOpen, openDialog, postpone, checkNow }),
    [status, dialogOpen, openDialog, postpone, checkNow],
  )
  return <UpdatesContext.Provider value={value}>{children}</UpdatesContext.Provider>
}

export function useUpdates() {
  const context = useContext(UpdatesContext)
  if (!context) throw new Error("useUpdates precisa estar dentro de UpdatesProvider")
  return context
}

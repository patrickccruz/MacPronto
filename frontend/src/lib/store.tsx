import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { api } from "./api"
import type { StepId, ViewId } from "./steps"
import type { AppInfo, PlanPayload, ScanPayload, Selection, Settings } from "./types"

const DEFAULT_SETTINGS: Settings = { theme: "system", policy_accepted: false, advanced: false, last_scan_id: null }

interface AppContextValue {
  info: AppInfo | null
  settings: Settings
  updateSettings: (changes: Partial<Settings>) => Promise<void>
  payload: ScanPayload | null
  setPayload: (payload: ScanPayload | null) => void
  setPlan: (plan: PlanPayload, selection: Selection) => void
  efiReady: boolean
  setEfiReady: (ready: boolean) => void
  view: ViewId
  go: (view: ViewId) => void
  resolvedTheme: "light" | "dark"
}

const AppContext = createContext<AppContextValue | null>(null)

function systemPrefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<AppInfo | null>(null)
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS)
  const [payload, setPayloadState] = useState<ScanPayload | null>(null)
  const [efiReady, setEfiReady] = useState(false)
  // ?view= serve só para inspecionar telas no modo de demonstração
  const [view, setView] = useState<ViewId>(() => (new URLSearchParams(window.location.search).get("view") as ViewId) || "welcome")
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  useEffect(() => {
    let active = true
    void (async () => {
      const appInfo = await api.appInfo()
      if (!active) return
      setInfo(appInfo)
      setSettings(appInfo.settings)
      const session = await api.sessionState()
      if (active && session) {
        setPayloadState(session)
        setView((current) => (current === "welcome" ? "report" : current))
      }
    })()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)")
    if (!media) return
    const listener = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    media.addEventListener("change", listener)
    return () => media.removeEventListener("change", listener)
  }, [])

  const resolvedTheme: "light" | "dark" =
    settings.theme === "system" ? (systemDark ? "dark" : "light") : settings.theme

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolvedTheme === "dark")
    document.documentElement.style.colorScheme = resolvedTheme
  }, [resolvedTheme])

  const updateSettings = useCallback(async (changes: Partial<Settings>) => {
    setSettings((previous) => ({ ...previous, ...changes }))
    const saved = await api.settingsUpdate(changes)
    setSettings(saved)
  }, [])

  const setPayload = useCallback((next: ScanPayload | null) => {
    setPayloadState(next)
    setEfiReady(false)
  }, [])

  const setPlan = useCallback((plan: PlanPayload, selection: Selection) => {
    setPayloadState((previous) => (previous ? { ...previous, plan, selection } : previous))
    setEfiReady(false)
  }, [])

  const go = useCallback((next: ViewId) => {
    setView(next)
    document.getElementById("main-scroll")?.scrollTo({ top: 0 })
  }, [])

  const value = useMemo(
    () => ({ info, settings, updateSettings, payload, setPayload, setPlan, efiReady, setEfiReady, view, go, resolvedTheme }),
    [info, settings, updateSettings, payload, setPayload, setPlan, efiReady, view, go, resolvedTheme],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) throw new Error("useApp precisa estar dentro de AppProvider")
  return context
}

export type { StepId }

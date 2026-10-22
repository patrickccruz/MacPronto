import { useMemo } from "react"

import { AppSidebar } from "@/components/AppSidebar"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { isMockMode } from "@/lib/bridge"
import { STEPS, type ViewId } from "@/lib/steps"
import { AppProvider, useApp } from "@/lib/store"
import { AboutPage } from "@/steps/AboutPage"
import { ComingSoon } from "@/steps/ComingSoon"
import { DiagnosisStep } from "@/steps/DiagnosisStep"
import { LogsPage } from "@/steps/LogsPage"
import { ReportStep } from "@/steps/ReportStep"
import { VersionStep } from "@/steps/VersionStep"
import { WelcomeStep } from "@/steps/WelcomeStep"

function CurrentView({ view }: { view: ViewId }) {
  switch (view) {
    case "welcome":
      return <WelcomeStep />
    case "diagnosis":
      return <DiagnosisStep />
    case "report":
      return <ReportStep />
    case "version":
      return <VersionStep />
    case "logs":
      return <LogsPage />
    case "about":
      return <AboutPage />
    default: {
      const step = STEPS.find((item) => item.id === view)
      return <ComingSoon title={step?.title ?? ""} description={step?.description ?? ""} />
    }
  }
}

function Shell() {
  const { view, payload, efiReady, settings, resolvedTheme } = useApp()

  const completed = useMemo(() => {
    const done = new Set<ViewId>()
    if (settings.policy_accepted) done.add("welcome")
    if (payload) {
      done.add("diagnosis")
      done.add("report")
      if (payload.plan) done.add("version")
    }
    if (efiReady) done.add("efi")
    return done
  }, [settings.policy_accepted, payload, efiReady])

  return (
    <div className="flex h-full">
      <AppSidebar completed={completed} />
      <main id="main-scroll" className="scroll-thin min-w-0 flex-1 overflow-y-auto">
        {isMockMode() && (
          <div className="border-b bg-tweak/15 px-8 py-1.5 text-center text-xs text-foreground">
            Modo de demonstração: os dados são de exemplo e nada é executado de verdade.
          </div>
        )}
        <div className="mx-auto max-w-6xl px-8 py-8">
          <CurrentView view={view} />
        </div>
      </main>
      <Toaster theme={resolvedTheme} position="bottom-right" richColors closeButton />
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <TooltipProvider delayDuration={250}>
        <Shell />
      </TooltipProvider>
    </AppProvider>
  )
}

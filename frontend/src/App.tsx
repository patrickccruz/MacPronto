import { useMemo } from "react"

import { AppSidebar } from "@/components/AppSidebar"
import { TaskDock } from "@/components/TaskDock"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { BackgroundTasksProvider } from "@/lib/backgroundTasks"
import { isMockMode } from "@/lib/bridge"
import type { ViewId } from "@/lib/steps"
import { AppProvider, useApp } from "@/lib/store"
import { AboutPage } from "@/steps/AboutPage"
import { DiagnosisStep } from "@/steps/DiagnosisStep"
import { EfiStep } from "@/steps/EfiStep"
import { GuideStep } from "@/steps/GuideStep"
import { LogsPage } from "@/steps/LogsPage"
import { PendriveStep } from "@/steps/PendriveStep"
import { ReportStep } from "@/steps/ReportStep"
import { UsbStep } from "@/steps/UsbStep"
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
    case "efi":
      return <EfiStep />
    case "usb":
      return <UsbStep />
    case "pendrive":
      return <PendriveStep />
    case "guide":
      return <GuideStep />
    case "logs":
      return <LogsPage />
    case "about":
      return <AboutPage />
    default:
      return null
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
      <TaskDock />
      <Toaster theme={resolvedTheme} position="bottom-right" richColors closeButton />
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <BackgroundTasksProvider>
        <TooltipProvider delayDuration={250}>
          <Shell />
        </TooltipProvider>
      </BackgroundTasksProvider>
    </AppProvider>
  )
}
